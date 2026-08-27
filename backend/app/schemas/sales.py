from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SalesItemCreate(BaseModel):
    product_id: int
    unit_type: Literal["carton", "piece"] = "piece"
    quantity: Decimal = Field(..., gt=0)
    rate: Decimal = Field(..., ge=0)
    discount_amount: Decimal = Field(Decimal("0"), ge=0)


class SalesInvoiceCreate(BaseModel):
    customer_id: int
    invoice_date: date
    sale_type: Literal["cash", "credit"] = "cash"
    discount_amount: Decimal = Field(Decimal("0"), ge=0)
    paid_amount: Decimal | None = Field(None, ge=0)
    override_credit_limit: bool = False
    items: list[SalesItemCreate] = Field(..., min_length=1)


class SalesItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sales_item_id: int
    product_id: int
    unit_type: str
    quantity: Decimal
    quantity_in_pieces: Decimal
    rate: Decimal
    discount_amount: Decimal
    total_amount: Decimal


class SalesInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: int
    invoice_number: str
    customer_id: int
    invoice_date: date
    sale_type: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    created_by: int
    created_at: datetime
    updated_at: datetime
    items: list[SalesItemResponse] = []
