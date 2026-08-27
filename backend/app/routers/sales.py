from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_current_user, get_db, get_optional_or_system_user
from app.core.security import AppException
from app.models.customer import Customer, CustomerLedger
from app.models.product import Product, StockLedger
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.models.user import User
from app.schemas.common import Page
from app.schemas.sales import SalesInvoiceCreate, SalesInvoiceResponse
from app.services.invoicing import next_sales_invoice_number, to_pieces
from app.services.pdf import sales_invoice_pdf

router = APIRouter(prefix="/sales-invoices", tags=["Sales"])


@router.get("", response_model=Page[SalesInvoiceResponse])
async def list_sales_invoices(
    pg: Pagination = Depends(),
    customer_id: int | None = None,
    sale_type: str | None = Query(None, pattern="^(cash|credit)$"),
    created_by: str | None = Query(None, description="user_id or 'me'"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(SalesInvoice)
    count_q = select(func.count()).select_from(SalesInvoice)

    def apply(cond):
        nonlocal query, count_q
        query, count_q = query.where(cond), count_q.where(cond)

    # sales_entry may only ever see their own invoices.
    if current_user.role != "admin":
        apply(SalesInvoice.created_by == current_user.user_id)
    elif created_by is not None:
        resolved = current_user.user_id if created_by == "me" else int(created_by)
        apply(SalesInvoice.created_by == resolved)

    if customer_id is not None:
        apply(SalesInvoice.customer_id == customer_id)
    if sale_type is not None:
        apply(SalesInvoice.sale_type == sale_type)
    if date_from is not None:
        apply(SalesInvoice.invoice_date >= date_from)
    if date_to is not None:
        apply(SalesInvoice.invoice_date <= date_to)

    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            query.order_by(SalesInvoice.invoice_id.desc()).limit(pg.limit).offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("", response_model=SalesInvoiceResponse, status_code=201)
async def create_sales_invoice(
    payload: SalesInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_or_system_user),
):
    if payload.invoice_date > date.today():
        raise AppException(400, "Invoice date cannot be in the future", "INVALID_DATE")

    customer = await db.get(Customer, payload.customer_id)
    if customer is None or not customer.is_active:
        raise AppException(404, "Customer not found or inactive", "CUSTOMER_NOT_FOUND")

    product_ids = {item.product_id for item in payload.items}
    products = {
        p.product_id: p
        for p in (
            await db.execute(select(Product).where(Product.product_id.in_(product_ids)))
        ).scalars().all()
    }

    computed_items: list[dict] = []
    subtotal = Decimal("0")
    required_pieces: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for item in payload.items:
        product = products.get(item.product_id)
        if product is None or not product.is_active:
            raise AppException(404, f"Product {item.product_id} not found or inactive", "PRODUCT_NOT_FOUND")
        qty_pieces = to_pieces(item.unit_type, item.quantity, product.pieces_per_carton)
        line_total = (item.quantity * item.rate - item.discount_amount).quantize(Decimal("0.01"))
        if line_total < 0:
            raise AppException(400, "Line discount cannot exceed line amount", "INVALID_DISCOUNT")
        subtotal += line_total
        required_pieces[item.product_id] += qty_pieces
        computed_items.append(
            {
                "product_id": item.product_id,
                "unit_type": item.unit_type,
                "quantity": item.quantity,
                "quantity_in_pieces": qty_pieces,
                "rate": item.rate,
                "discount_amount": item.discount_amount,
            }
        )

    # Stock availability check (aggregated per product).
    for product_id, needed in required_pieces.items():
        product = products[product_id]
        if product.current_stock < needed:
            raise AppException(
                400,
                f"Insufficient stock for '{product.product_name}': "
                f"available {product.current_stock}, required {needed}",
                "INSUFFICIENT_STOCK",
            )

    total_amount = (subtotal - payload.discount_amount).quantize(Decimal("0.01"))
    if total_amount < 0:
        raise AppException(400, "Discount cannot exceed subtotal", "INVALID_DISCOUNT")

    if payload.sale_type == "cash":
        paid_amount = total_amount if payload.paid_amount is None else payload.paid_amount
    else:
        paid_amount = payload.paid_amount or Decimal("0")
    if paid_amount > total_amount:
        raise AppException(400, "Paid amount cannot exceed invoice total", "INVALID_PAID_AMOUNT")

    # Credit limit enforcement for credit sales (0 credit_limit means unlimited).
    if payload.sale_type == "credit" and customer.credit_limit > 0:
        projected = customer.current_balance + total_amount
        if projected > customer.credit_limit and not (
            payload.override_credit_limit and current_user.role == "admin"
        ):
            raise AppException(
                400,
                f"Credit limit exceeded: balance {customer.current_balance} + invoice {total_amount} "
                f"> limit {customer.credit_limit}",
                "CREDIT_LIMIT_EXCEEDED",
            )

    invoice_number = await next_sales_invoice_number(db)

    invoice = SalesInvoice(
        invoice_number=invoice_number,
        customer_id=payload.customer_id,
        invoice_date=payload.invoice_date,
        sale_type=payload.sale_type,
        subtotal_amount=subtotal,
        discount_amount=payload.discount_amount,
        paid_amount=paid_amount,
        created_by=current_user.user_id,
    )
    db.add(invoice)
    await db.flush()

    item_rows = [SalesInvoiceItem(invoice_id=invoice.invoice_id, **ci) for ci in computed_items]
    for row in item_rows:
        db.add(row)
    await db.flush()  # assigns sales_item_id to each row

    # ── Stock update (replaces the missing DB trigger trg_salesitem_after_insert) ──
    for row in item_rows:
        await db.execute(
            update(Product)
            .where(Product.product_id == row.product_id)
            .values(current_stock=Product.current_stock - row.quantity_in_pieces)
        )
        new_balance = (
            await db.execute(select(Product.current_stock).where(Product.product_id == row.product_id))
        ).scalar_one()
        db.add(
            StockLedger(
                product_id=row.product_id,
                transaction_type="sale",
                reference_table="sales_invoice_items",
                reference_id=row.sales_item_id,
                quantity_change=-row.quantity_in_pieces,
                balance_after=new_balance,
            )
        )

    # ── Customer balance + ledger (replaces the missing DB trigger trg_salesinv_after_insert) ──
    await db.execute(
        update(Customer)
        .where(Customer.customer_id == invoice.customer_id)
        .values(current_balance=Customer.current_balance + total_amount)
    )
    bal = (
        await db.execute(select(Customer.current_balance).where(Customer.customer_id == invoice.customer_id))
    ).scalar_one()
    db.add(
        CustomerLedger(
            customer_id=invoice.customer_id,
            transaction_date=invoice.invoice_date,
            transaction_type="invoice",
            reference_table="sales_invoices",
            reference_id=invoice.invoice_id,
            debit=total_amount,
            credit=Decimal("0"),
            balance_after=bal,
        )
    )
    if paid_amount > 0:
        await db.execute(
            update(Customer)
            .where(Customer.customer_id == invoice.customer_id)
            .values(current_balance=Customer.current_balance - paid_amount)
        )
        bal = (
            await db.execute(select(Customer.current_balance).where(Customer.customer_id == invoice.customer_id))
        ).scalar_one()
        db.add(
            CustomerLedger(
                customer_id=invoice.customer_id,
                transaction_date=invoice.invoice_date,
                transaction_type="payment",
                reference_table="sales_invoices",
                reference_id=invoice.invoice_id,
                debit=Decimal("0"),
                credit=paid_amount,
                balance_after=bal,
            )
        )

    await db.commit()
    invoice_id = invoice.invoice_id
    db.expire_all()
    return await db.get(SalesInvoice, invoice_id)


@router.get("/{invoice_id}", response_model=SalesInvoiceResponse)
async def get_sales_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise AppException(404, "Sales invoice not found", "SALES_NOT_FOUND")
    if current_user.role != "admin" and invoice.created_by != current_user.user_id:
        raise AppException(403, "You can only view your own invoices", "FORBIDDEN")
    return invoice


@router.get("/{invoice_id}/pdf")
async def sales_invoice_pdf_endpoint(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise AppException(404, "Sales invoice not found", "SALES_NOT_FOUND")
    if current_user.role != "admin" and invoice.created_by != current_user.user_id:
        raise AppException(403, "You can only view your own invoices", "FORBIDDEN")
    customer = await db.get(Customer, invoice.customer_id)
    product_ids = {it.product_id for it in invoice.items}
    names = {
        p.product_id: p.product_name
        for p in (
            await db.execute(select(Product).where(Product.product_id.in_(product_ids)))
        ).scalars().all()
    }
    pdf_bytes = sales_invoice_pdf(invoice, customer, names)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'},
    )