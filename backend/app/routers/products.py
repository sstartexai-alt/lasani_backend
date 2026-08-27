from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_current_user, get_db, require_role
from app.core.security import AppException
from app.models.product import Product, ProductCategory, StockLedger
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    StockLedgerResponse,
)

router = APIRouter(tags=["Products & Stock"])
admin_only = require_role("admin")


# ---------------- Categories ----------------
@router.get("/categories", response_model=Page[CategoryResponse])
async def list_categories(
    pg: Pagination = Depends(), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    total = (await db.execute(select(func.count()).select_from(ProductCategory))).scalar_one()
    rows = (
        await db.execute(
            select(ProductCategory).order_by(ProductCategory.category_name).limit(pg.limit).offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    payload: CategoryCreate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    exists = (
        await db.execute(
            select(ProductCategory).where(ProductCategory.category_name == payload.category_name)
        )
    ).scalar_one_or_none()
    if exists:
        raise AppException(400, "Category name already exists", "DUPLICATE_CATEGORY")
    category = ProductCategory(category_name=payload.category_name)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    category = await db.get(ProductCategory, category_id)
    if category is None:
        raise AppException(404, "Category not found", "CATEGORY_NOT_FOUND")
    category.category_name = payload.category_name
    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/categories/{category_id}", response_model=Message)
async def delete_category(
    category_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    category = await db.get(ProductCategory, category_id)
    if category is None:
        raise AppException(404, "Category not found", "CATEGORY_NOT_FOUND")
    await db.delete(category)
    await db.commit()
    return Message(detail="Category deleted")


# ---------------- Products ----------------
@router.get("/products", response_model=Page[ProductResponse])
async def list_products(
    pg: Pagination = Depends(),
    search: str | None = Query(None, description="Filter by name or SKU"),
    category_id: int | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Product)
    count_q = select(func.count()).select_from(Product)
    if search:
        cond = Product.product_name.like(f"%{search}%") | Product.sku.like(f"%{search}%")
        query = query.where(cond)
        count_q = count_q.where(cond)
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
        count_q = count_q.where(Product.category_id == category_id)
    if is_active is not None:
        query = query.where(Product.is_active == (1 if is_active else 0))
        count_q = count_q.where(Product.is_active == (1 if is_active else 0))

    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(query.order_by(Product.product_name).limit(pg.limit).offset(pg.offset))
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)


@router.get("/products/low-stock", response_model=list[ProductResponse])
async def low_stock_products(db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = (
        await db.execute(
            select(Product)
            .where(Product.is_active == 1, Product.current_stock <= Product.low_stock_threshold)
            .order_by(Product.product_name)
        )
    ).scalars().all()
    return list(rows)


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    payload: ProductCreate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    if payload.category_id is not None:
        category = await db.get(ProductCategory, payload.category_id)
        if category is None:
            raise AppException(404, "Category not found", "CATEGORY_NOT_FOUND")
    exists = (
        await db.execute(select(Product).where(Product.sku == payload.sku))
    ).scalar_one_or_none()
    if exists:
        raise AppException(400, "SKU already exists", "DUPLICATE_SKU")

    product = Product(
        sku=payload.sku,
        product_name=payload.product_name,
        category_id=payload.category_id,
        unit_type=payload.unit_type,
        pieces_per_carton=payload.pieces_per_carton,
        opening_stock=payload.opening_stock,
        current_stock=payload.opening_stock,  # trigger logs the opening ledger row
        purchase_price=payload.purchase_price,
        sale_price=payload.sale_price,
        low_stock_threshold=payload.low_stock_threshold,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
):
    product = await db.get(Product, product_id)
    if product is None:
        raise AppException(404, "Product not found", "PRODUCT_NOT_FOUND")
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    product = await db.get(Product, product_id)
    if product is None:
        raise AppException(404, "Product not found", "PRODUCT_NOT_FOUND")
    data = payload.model_dump(exclude_unset=True)
    if data.get("category_id") is not None:
        category = await db.get(ProductCategory, data["category_id"])
        if category is None:
            raise AppException(404, "Category not found", "CATEGORY_NOT_FOUND")
    if "sku" in data and data["sku"] != product.sku:
        dup = (
            await db.execute(select(Product).where(Product.sku == data["sku"]))
        ).scalar_one_or_none()
        if dup:
            raise AppException(400, "SKU already exists", "DUPLICATE_SKU")
    if "is_active" in data:
        product.is_active = 1 if data.pop("is_active") else 0
    for key, value in data.items():
        setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/products/{product_id}", response_model=Message)
async def deactivate_product(
    product_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    product = await db.get(Product, product_id)
    if product is None:
        raise AppException(404, "Product not found", "PRODUCT_NOT_FOUND")
    product.is_active = 0
    await db.commit()
    return Message(detail="Product deactivated")


# ---------------- Stock ledger ----------------
@router.get("/stock-ledger/{product_id}", response_model=Page[StockLedgerResponse])
async def stock_ledger(
    product_id: int,
    pg: Pagination = Depends(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    product = await db.get(Product, product_id)
    if product is None:
        raise AppException(404, "Product not found", "PRODUCT_NOT_FOUND")
    count_q = select(func.count()).select_from(StockLedger).where(StockLedger.product_id == product_id)
    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            select(StockLedger)
            .where(StockLedger.product_id == product_id)
            .order_by(StockLedger.stock_ledger_id)
            .limit(pg.limit)
            .offset(pg.offset)
        )
    ).scalars().all()
    return Page.create(list(rows), total, pg.page, pg.page_size)
