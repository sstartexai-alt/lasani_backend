from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DECIMAL, Date, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    credit_limit: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    current_balance: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class CustomerLedger(Base):
    __tablename__ = "customer_ledger"

    ledger_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[str] = mapped_column(
        Enum("opening_balance", "invoice", "payment", "adjustment", name="cust_ledger_type"),
        nullable=False,
    )
    reference_table: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    debit: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    credit: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())


class CustomerPayment(Base):
    __tablename__ = "customer_payments"

    payment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("sales_invoices.invoice_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(
        Enum("cash", "bank", name="cust_pay_mode"), nullable=False, default="cash"
    )
    reference_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    received_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())