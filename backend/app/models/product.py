from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Computed,
    DECIMAL,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductCategory(Base):
    __tablename__ = "product_categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_categories.category_id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
    )
    unit_type: Mapped[str] = mapped_column(
        Enum("carton", "piece", "both", name="product_unit_type"), nullable=False, default="piece"
    )
    pieces_per_carton: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    opening_stock: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, default=0)
    current_stock: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, default=0)
    purchase_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    stock_value: Mapped[Decimal] = mapped_column(
        DECIMAL(14, 2), Computed("(current_stock * purchase_price)", persisted=True)
    )
    sale_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    low_stock_threshold: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    stock_ledger_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(
        Enum("opening", "purchase", "sale", "adjustment", name="stock_txn_type"), nullable=False
    )
    reference_table: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quantity_change: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
