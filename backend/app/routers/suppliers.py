from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_db, require_role
from app.core.security import AppException
from app.models.supplier import Supplier, SupplierLedger
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.supplier import (
    SupplierCreate,
    SupplierLedgerRow,
    SupplierResponse,
    SupplierUpdate,
)

router = APIRouter(tags=["Suppliers"])
admin_only = require_role("admin")


@router.get("/suppliers", response_model=Page[SupplierResponse])
async def list_suppliers(
    pg: Pagination = Depends(),
    search: str | None = Query(None),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(Supplier)
    count_q = select(func.count()).select_from(Supplier)
    if search:
        cond = Supplier.supplier_name.like(f"%{search}%")
        query, count_q = query.where(cond), count_q.where(cond)
    if is_active is not None:
        flag = 1 if is_active else 0
        query, count_q = query.where(Supplier.is_active == flag), count_q.where(Supplier.is_active == flag)
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(query.order_by(Supplier.supplier_name).limit(pg.limit).offset(pg.offset))
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    payload: SupplierCreate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    supplier = Supplier(
        supplier_name=payload.supplier_name,
        contact_number=payload.contact_number,
        address=payload.address,
        opening_balance=payload.opening_balance,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise AppException(404, "Supplier not found", "SUPPLIER_NOT_FOUND")
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise AppException(404, "Supplier not found", "SUPPLIER_NOT_FOUND")
    data = payload.model_dump(exclude_unset=True)
    if "is_active" in data:
        supplier.is_active = 1 if data.pop("is_active") else 0
    for key, value in data.items():
        setattr(supplier, key, value)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", response_model=Message)
async def deactivate_supplier(
    supplier_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise AppException(404, "Supplier not found", "SUPPLIER_NOT_FOUND")
    supplier.is_active = 0
    await db.commit()
    return Message(detail="Supplier deactivated")


@router.get("/supplier-ledger/{supplier_id}", response_model=Page[SupplierLedgerRow])
async def supplier_ledger(
    supplier_id: int,
    pg: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise AppException(404, "Supplier not found", "SUPPLIER_NOT_FOUND")
    count_q = (
        select(func.count()).select_from(SupplierLedger).where(SupplierLedger.supplier_id == supplier_id)
    )
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            select(SupplierLedger)
            .where(SupplierLedger.supplier_id == supplier_id)
            .order_by(SupplierLedger.ledger_id)
            .limit(pg.limit)
            .offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)
