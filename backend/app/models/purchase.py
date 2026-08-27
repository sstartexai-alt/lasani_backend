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


class PurchaseInvoice(Base):
    __tablename__ = "purchase_invoices"

    purchase_invoice_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    outstanding_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), Computed("(total_amount - paid_amount)", persisted=True)
    )
    payment_status: Mapped[str] = mapped_column(
        Enum("unpaid", "partial", "paid", name="purch_pay_status"),
        Computed(
            "(case when (paid_amount <= 0) then 'unpaid' "
            "when (paid_amount >= total_amount) then 'paid' else 'partial' end)",
            persisted=True,
        ),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    items: Mapped[list["PurchaseInvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseInvoiceItem(Base):
    __tablename__ = "purchase_invoice_items"

    purchase_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    purchase_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_invoices.purchase_invoice_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.product_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    unit_type: Mapped[str] = mapped_column(
        Enum("carton", "piece", name="purch_item_unit"), nullable=False, default="piece"
    )
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    quantity_in_pieces: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    purchase_rate: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), Computed("(quantity * purchase_rate)", persisted=True)
    )

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="items")
