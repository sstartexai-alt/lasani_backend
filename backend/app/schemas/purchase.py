from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PurchaseItemCreate(BaseModel):
    product_id: int
    unit_type: Literal["carton", "piece"] = "piece"
    quantity: Decimal = Field(..., gt=0)
    purchase_rate: Decimal = Field(..., ge=0)


class PurchaseInvoiceCreate(BaseModel):
    supplier_id: int
    purchase_date: date
    paid_amount: Decimal = Field(Decimal("0"), ge=0)
    payment_mode: Literal["cash", "bank"] = "cash"
    invoice_number: str | None = Field(None, max_length=50)
    items: list[PurchaseItemCreate] = Field(..., min_length=1)


class PurchaseItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    purchase_item_id: int
    product_id: int
    unit_type: str
    quantity: Decimal
    quantity_in_pieces: Decimal
    purchase_rate: Decimal
    total_amount: Decimal


class PurchaseInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    purchase_invoice_id: int
    invoice_number: str
    supplier_id: int
    purchase_date: date
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    payment_status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseItemResponse] = []
