from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=150)
    area: str | None = Field(None, max_length=100)
    contact_number: str | None = Field(None, max_length=30)
    opening_balance: Decimal = Field(Decimal("0"), ge=0)
    credit_limit: Decimal = Field(Decimal("0"), ge=0)


class CustomerUpdate(BaseModel):
    customer_name: str | None = Field(None, min_length=1, max_length=150)
    area: str | None = Field(None, max_length=100)
    contact_number: str | None = Field(None, max_length=30)
    credit_limit: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: int
    customer_name: str
    area: str | None
    contact_number: str | None
    opening_balance: Decimal
    credit_limit: Decimal
    current_balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerLedgerRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ledger_id: int
    customer_id: int
    transaction_date: date
    transaction_type: str
    reference_table: str | None
    reference_id: int | None
    debit: Decimal
    credit: Decimal
    balance_after: Decimal
    created_at: datetime
