from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_current_user, get_db, require_role
from app.core.security import AppException
from app.models.customer import Customer, CustomerLedger
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.customer import (
    CustomerCreate,
    CustomerLedgerRow,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter(tags=["Customers"])
admin_only = require_role("admin")


@router.get("/customers", response_model=Page[CustomerResponse])
async def list_customers(
    pg: Pagination = Depends(),
    search: str | None = Query(None),
    area: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Customer)
    count_q = select(func.count()).select_from(Customer)
    if search:
        cond = Customer.customer_name.like(f"%{search}%")
        query, count_q = query.where(cond), count_q.where(cond)
    if area:
        query, count_q = query.where(Customer.area == area), count_q.where(Customer.area == area)
    if is_active is not None:
        flag = 1 if is_active else 0
        query, count_q = query.where(Customer.is_active == flag), count_q.where(Customer.is_active == flag)
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(query.order_by(Customer.customer_name).limit(pg.limit).offset(pg.offset))
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("/customers", response_model=CustomerResponse, status_code=201)
async def create_customer(
    payload: CustomerCreate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    customer = Customer(
        customer_name=payload.customer_name,
        area=payload.area,
        contact_number=payload.contact_number,
        opening_balance=payload.opening_balance,
        credit_limit=payload.credit_limit,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise AppException(404, "Customer not found", "CUSTOMER_NOT_FOUND")
    return customer


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise AppException(404, "Customer not found", "CUSTOMER_NOT_FOUND")
    data = payload.model_dump(exclude_unset=True)
    if "is_active" in data:
        customer.is_active = 1 if data.pop("is_active") else 0
    for key, value in data.items():
        setattr(customer, key, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete("/customers/{customer_id}", response_model=Message)
async def deactivate_customer(
    customer_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise AppException(404, "Customer not found", "CUSTOMER_NOT_FOUND")
    customer.is_active = 0
    await db.commit()
    return Message(detail="Customer deactivated")


@router.get("/customers/{customer_id}/ledger", response_model=Page[CustomerLedgerRow])
async def customer_ledger(
    customer_id: int,
    pg: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise AppException(404, "Customer not found", "CUSTOMER_NOT_FOUND")
    count_q = (
        select(func.count()).select_from(CustomerLedger).where(CustomerLedger.customer_id == customer_id)
    )
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            select(CustomerLedger)
            .where(CustomerLedger.customer_id == customer_id)
            .order_by(CustomerLedger.ledger_id)
            .limit(pg.limit)
            .offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


# Alias endpoint: /customer-ledger/{customer_id}
ledger_router = APIRouter(tags=["Customers"])


@ledger_router.get("/customer-ledger/{customer_id}", response_model=Page[CustomerLedgerRow])
async def customer_ledger_alias(
    customer_id: int,
    pg: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    return await customer_ledger(customer_id, pg, db, _)
