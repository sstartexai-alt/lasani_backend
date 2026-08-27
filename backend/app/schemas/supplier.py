from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    supplier_name: str = Field(..., min_length=1, max_length=150)
    contact_number: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=255)
    opening_balance: Decimal = Field(Decimal("0"), ge=0)


class SupplierUpdate(BaseModel):
    supplier_name: str | None = Field(None, min_length=1, max_length=150)
    contact_number: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    supplier_id: int
    supplier_name: str
    contact_number: str | None
    address: str | None
    opening_balance: Decimal
    current_balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierLedgerRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ledger_id: int
    supplier_id: int
    transaction_date: date
    transaction_type: str
    reference_table: str | None
    reference_id: int | None
    debit: Decimal
    credit: Decimal
    balance_after: Decimal
    created_at: datetime
