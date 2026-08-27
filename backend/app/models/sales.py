from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Computed,
    DECIMAL,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"

    invoice_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    sale_type: Mapped[str] = mapped_column(
        Enum("cash", "credit", name="sale_type"), nullable=False, default="cash"
    )
    subtotal_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), Computed("(subtotal_amount - discount_amount)", persisted=True)
    )
    paid_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    outstanding_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2),
        Computed("((subtotal_amount - discount_amount) - paid_amount)", persisted=True),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    items: Mapped[list["SalesInvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )


class SalesInvoiceItem(Base):
    __tablename__ = "sales_invoice_items"

    sales_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("sales_invoices.invoice_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    unit_type: Mapped[str] = mapped_column(
        Enum("carton", "piece", name="sales_item_unit"), nullable=False, default="piece"
    )
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    quantity_in_pieces: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    rate: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), Computed("((quantity * rate) - discount_amount)", persisted=True)
    )

    invoice: Mapped["SalesInvoice"] = relationship(back_populates="items")
