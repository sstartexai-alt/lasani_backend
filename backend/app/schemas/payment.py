from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CustomerPaymentCreate(BaseModel):
    customer_id: int
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    payment_mode: Literal["cash", "bank"] = "cash"
    reference_note: str | None = Field(None, max_length=255)
    invoice_id: int | None = None  # optional -- if set, this payment also updates that invoice's paid_amount


class CustomerPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: int
    customer_id: int
    payment_date: date
    amount: Decimal
    payment_mode: str
    reference_note: str | None
    received_by: int
    created_at: datetime


class SupplierPaymentCreate(BaseModel):
    supplier_id: int
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    payment_mode: Literal["cash", "bank"] = "cash"
    reference_note: str | None = Field(None, max_length=255)


class SupplierPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: int
    supplier_id: int
    payment_date: date
    amount: Decimal
    payment_mode: str
    reference_note: str | None
    paid_by: int
    created_at: datetime