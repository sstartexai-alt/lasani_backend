from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_db, require_role
from app.core.security import AppException
from app.models.product import Product, StockLedger
from app.models.purchase import PurchaseInvoice, PurchaseInvoiceItem
from app.models.supplier import Supplier, SupplierLedger
from app.models.user import User
from app.schemas.common import Page
from app.schemas.purchase import PurchaseInvoiceCreate, PurchaseInvoiceResponse
from app.services.invoicing import next_purchase_invoice_number, to_pieces
from app.services.pdf import purchase_invoice_pdf

router = APIRouter(prefix="/purchase-invoices", tags=["Purchases"])
admin_only = require_role("admin")


@router.get("", response_model=Page[PurchaseInvoiceResponse])
async def list_purchase_invoices(
    pg: Pagination = Depends(),
    supplier_id: int | None = None,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(PurchaseInvoice)
    count_q = select(func.count()).select_from(PurchaseInvoice)
    if supplier_id is not None:
        query, count_q = query.where(PurchaseInvoice.supplier_id == supplier_id), count_q.where(
            PurchaseInvoice.supplier_id == supplier_id
        )
    if date_from is not None:
        query, count_q = query.where(PurchaseInvoice.purchase_date >= date_from), count_q.where(
            PurchaseInvoice.purchase_date >= date_from
        )
    if date_to is not None:
        query, count_q = query.where(PurchaseInvoice.purchase_date <= date_to), count_q.where(
            PurchaseInvoice.purchase_date <= date_to
        )
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            query.order_by(PurchaseInvoice.purchase_invoice_id.desc()).limit(pg.limit).offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("", response_model=PurchaseInvoiceResponse, status_code=201)
async def create_purchase_invoice(
    payload: PurchaseInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    if payload.purchase_date > date.today():
        raise AppException(400, "Purchase date cannot be in the future", "INVALID_DATE")

    supplier = await db.get(Supplier, payload.supplier_id)
    if supplier is None or not supplier.is_active:
        raise AppException(404, "Supplier not found or inactive", "SUPPLIER_NOT_FOUND")

    # Validate products and pre-compute line values.
    product_ids = {item.product_id for item in payload.items}
    products = {
        p.product_id: p
        for p in (
            await db.execute(select(Product).where(Product.product_id.in_(product_ids)))
        ).scalars().all()
    }
    computed_items: list[dict] = []
    total_amount = Decimal("0")
    for item in payload.items:
        product = products.get(item.product_id)
        if product is None or not product.is_active:
            raise AppException(404, f"Product {item.product_id} not found or inactive", "PRODUCT_NOT_FOUND")
        qty_pieces = to_pieces(item.unit_type, item.quantity, product.pieces_per_carton)
        line_total = (item.quantity * item.purchase_rate).quantize(Decimal("0.01"))
        total_amount += line_total
        computed_items.append(
            {
                "product_id": item.product_id,
                "unit_type": item.unit_type,
                "quantity": item.quantity,
                "quantity_in_pieces": qty_pieces,
                "purchase_rate": item.purchase_rate,
            }
        )

    if payload.paid_amount > total_amount:
        raise AppException(400, "Paid amount cannot exceed invoice total", "INVALID_PAID_AMOUNT")

    invoice_number = payload.invoice_number or await next_purchase_invoice_number(db)

    # Insert header first, then items.
    invoice = PurchaseInvoice(
        invoice_number=invoice_number,
        supplier_id=payload.supplier_id,
        purchase_date=payload.purchase_date,
        total_amount=total_amount,
        paid_amount=payload.paid_amount,
        created_by=current_user.user_id,
    )
    db.add(invoice)
    await db.flush()

    item_rows = [PurchaseInvoiceItem(purchase_invoice_id=invoice.purchase_invoice_id, **ci) for ci in computed_items]
    for row in item_rows:
        db.add(row)
    await db.flush()  # assigns purchase_item_id to each row

    # ── Stock update (replaces the missing DB trigger trg_purchitem_after_insert) ──
    # Same effect: current_stock += quantity_in_pieces, then one stock_ledger row per item.
    for row in item_rows:
        await db.execute(
            update(Product)
            .where(Product.product_id == row.product_id)
            .values(current_stock=Product.current_stock + row.quantity_in_pieces)
        )
        new_balance = (
            await db.execute(select(Product.current_stock).where(Product.product_id == row.product_id))
        ).scalar_one()
        db.add(
            StockLedger(
                product_id=row.product_id,
                transaction_type="purchase",
                reference_table="purchase_invoice_items",
                reference_id=row.purchase_item_id,
                quantity_change=row.quantity_in_pieces,
                balance_after=new_balance,
            )
        )

    # ── Supplier balance + ledger (replaces the missing DB trigger trg_purchinv_after_insert) ──
    await db.execute(
        update(Supplier)
        .where(Supplier.supplier_id == invoice.supplier_id)
        .values(current_balance=Supplier.current_balance + total_amount)
    )
    bal = (
        await db.execute(select(Supplier.current_balance).where(Supplier.supplier_id == invoice.supplier_id))
    ).scalar_one()
    db.add(
        SupplierLedger(
            supplier_id=invoice.supplier_id,
            transaction_date=invoice.purchase_date,
            transaction_type="purchase",
            reference_table="purchase_invoices",
            reference_id=invoice.purchase_invoice_id,
            debit=Decimal("0"),
            credit=total_amount,
            balance_after=bal,
        )
    )
    if payload.paid_amount > 0:
        await db.execute(
            update(Supplier)
            .where(Supplier.supplier_id == invoice.supplier_id)
            .values(current_balance=Supplier.current_balance - payload.paid_amount)
        )
        bal = (
            await db.execute(select(Supplier.current_balance).where(Supplier.supplier_id == invoice.supplier_id))
        ).scalar_one()
        db.add(
            SupplierLedger(
                supplier_id=invoice.supplier_id,
                transaction_date=invoice.purchase_date,
                transaction_type="payment",
                reference_table="purchase_invoices",
                reference_id=invoice.purchase_invoice_id,
                debit=payload.paid_amount,
                credit=Decimal("0"),
                balance_after=bal,
            )
        )

    await db.commit()
    # Re-read post-trigger values (fresh load pulls generated columns + items).
    invoice_id = invoice.purchase_invoice_id
    db.expire_all()
    return await db.get(PurchaseInvoice, invoice_id)


@router.get("/{purchase_invoice_id}", response_model=PurchaseInvoiceResponse)
async def get_purchase_invoice(
    purchase_invoice_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    invoice = await db.get(PurchaseInvoice, purchase_invoice_id)
    if invoice is None:
        raise AppException(404, "Purchase invoice not found", "PURCHASE_NOT_FOUND")
    return invoice


@router.get("/{purchase_invoice_id}/pdf")
async def purchase_invoice_pdf_endpoint(
    purchase_invoice_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    invoice = await db.get(PurchaseInvoice, purchase_invoice_id)
    if invoice is None:
        raise AppException(404, "Purchase invoice not found", "PURCHASE_NOT_FOUND")
    supplier = await db.get(Supplier, invoice.supplier_id)
    product_ids = {it.product_id for it in invoice.items}
    names = {
        p.product_id: p.product_name
        for p in (
            await db.execute(select(Product).where(Product.product_id.in_(product_ids)))
        ).scalars().all()
    }
    pdf_bytes = purchase_invoice_pdf(invoice, supplier, names)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'},
    )