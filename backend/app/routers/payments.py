from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_db, require_role
from app.core.security import AppException
from app.models.customer import Customer, CustomerLedger, CustomerPayment
from app.models.sales import SalesInvoice
from app.models.supplier import Supplier, SupplierLedger, SupplierPayment
from app.models.user import User
from app.schemas.common import Page
from app.schemas.payment import (
    CustomerPaymentCreate,
    CustomerPaymentResponse,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
)

router = APIRouter(tags=["Payments"])
admin_only = require_role("admin")


# ---------------- Customer payments ----------------
@router.get("/customer-payments", response_model=Page[CustomerPaymentResponse])
async def list_customer_payments(
    pg: Pagination = Depends(),
    customer_id: int | None = None,
    payment_mode: str | None = Query(None, pattern="^(cash|bank)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(CustomerPayment)
    count_q = select(func.count()).select_from(CustomerPayment)

    def apply(cond):
        nonlocal query, count_q
        query, count_q = query.where(cond), count_q.where(cond)

    if customer_id is not None:
        apply(CustomerPayment.customer_id == customer_id)
    if payment_mode is not None:
        apply(CustomerPayment.payment_mode == payment_mode)
    if date_from is not None:
        apply(CustomerPayment.payment_date >= date_from)
    if date_to is not None:
        apply(CustomerPayment.payment_date <= date_to)

    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            query.order_by(CustomerPayment.payment_id.desc()).limit(pg.limit).offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("/customer-payments", response_model=CustomerPaymentResponse, status_code=201)
async def create_customer_payment(
    payload: CustomerPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    if payload.payment_date > date.today():
        raise AppException(400, "Payment date cannot be in the future", "INVALID_DATE")
    customer = await db.get(Customer, payload.customer_id)
    if customer is None or not customer.is_active:
        raise AppException(404, "Customer not found or inactive", "CUSTOMER_NOT_FOUND")

    invoice = None
    if payload.invoice_id is not None:
        invoice = await db.get(SalesInvoice, payload.invoice_id)
        if invoice is None or invoice.customer_id != payload.customer_id:
            raise AppException(404, "Invoice not found for this customer", "INVOICE_NOT_FOUND")
        if payload.amount > invoice.outstanding_amount:
            raise AppException(
                400,
                f"Payment ({payload.amount}) exceeds invoice outstanding amount ({invoice.outstanding_amount})",
                "INVALID_PAID_AMOUNT",
            )

    payment = CustomerPayment(
        customer_id=payload.customer_id,
        invoice_id=payload.invoice_id,
        payment_date=payload.payment_date,
        amount=payload.amount,
        payment_mode=payload.payment_mode,
        reference_note=payload.reference_note,
        received_by=current_user.user_id,
    )
    db.add(payment)
    await db.flush()  # assigns payment_id

    if invoice is not None:
        # Applies this payment against the specific invoice's paid_amount.
        # outstanding_amount recalculates on its own (generated column).
        await db.execute(
            update(SalesInvoice)
            .where(SalesInvoice.invoice_id == invoice.invoice_id)
            .values(paid_amount=SalesInvoice.paid_amount + payload.amount)
        )

    # ── Customer balance + ledger (replaces the missing DB trigger trg_custpay_after_insert) ──
    await db.execute(
        update(Customer)
        .where(Customer.customer_id == payload.customer_id)
        .values(current_balance=Customer.current_balance - payload.amount)
    )
    bal = (
        await db.execute(select(Customer.current_balance).where(Customer.customer_id == payload.customer_id))
    ).scalar_one()
    db.add(
        CustomerLedger(
            customer_id=payload.customer_id,
            transaction_date=payload.payment_date,
            transaction_type="payment",
            reference_table="customer_payments",
            reference_id=payment.payment_id,
            debit=Decimal("0"),
            credit=payload.amount,
            balance_after=bal,
        )
    )

    await db.commit()
    await db.refresh(payment)
    return payment


# ---------------- Supplier payments ----------------
@router.get("/supplier-payments", response_model=Page[SupplierPaymentResponse])
async def list_supplier_payments(
    pg: Pagination = Depends(),
    supplier_id: int | None = None,
    payment_mode: str | None = Query(None, pattern="^(cash|bank)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(SupplierPayment)
    count_q = select(func.count()).select_from(SupplierPayment)

    def apply(cond):
        nonlocal query, count_q
        query, count_q = query.where(cond), count_q.where(cond)

    if supplier_id is not None:
        apply(SupplierPayment.supplier_id == supplier_id)
    if payment_mode is not None:
        apply(SupplierPayment.payment_mode == payment_mode)
    if date_from is not None:
        apply(SupplierPayment.payment_date >= date_from)
    if date_to is not None:
        apply(SupplierPayment.payment_date <= date_to)

    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            query.order_by(SupplierPayment.payment_id.desc()).limit(pg.limit).offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("/supplier-payments", response_model=SupplierPaymentResponse, status_code=201)
async def create_supplier_payment(
    payload: SupplierPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    if payload.payment_date > date.today():
        raise AppException(400, "Payment date cannot be in the future", "INVALID_DATE")
    supplier = await db.get(Supplier, payload.supplier_id)
    if supplier is None or not supplier.is_active:
        raise AppException(404, "Supplier not found or inactive", "SUPPLIER_NOT_FOUND")

    payment = SupplierPayment(
        supplier_id=payload.supplier_id,
        payment_date=payload.payment_date,
        amount=payload.amount,
        payment_mode=payload.payment_mode,
        reference_note=payload.reference_note,
        paid_by=current_user.user_id,
    )
    db.add(payment)
    await db.flush()  # assigns payment_id

    # ── Supplier balance + ledger (replaces the missing DB trigger trg_suppay_after_insert) ──
    await db.execute(
        update(Supplier)
        .where(Supplier.supplier_id == payload.supplier_id)
        .values(current_balance=Supplier.current_balance - payload.amount)
    )
    bal = (
        await db.execute(select(Supplier.current_balance).where(Supplier.supplier_id == payload.supplier_id))
    ).scalar_one()
    db.add(
        SupplierLedger(
            supplier_id=payload.supplier_id,
            transaction_date=payload.payment_date,
            transaction_type="payment",
            reference_table="supplier_payments",
            reference_id=payment.payment_id,
            debit=payload.amount,
            credit=Decimal("0"),
            balance_after=bal,
        )
    )

    await db.commit()
    await db.refresh(payment)
    return payment