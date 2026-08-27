from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---- Categories ----
class CategoryCreate(BaseModel):
    category_name: str = Field(..., min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str
    created_at: datetime


# ---- Products ----
class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    product_name: str = Field(..., min_length=1, max_length=150)
    category_id: int | None = None
    unit_type: Literal["carton", "piece", "both"] = "piece"
    pieces_per_carton: int = Field(1, ge=1)
    opening_stock: Decimal = Field(Decimal("0"), ge=0)
    purchase_price: Decimal = Field(Decimal("0"), ge=0)
    sale_price: Decimal = Field(Decimal("0"), ge=0)
    low_stock_threshold: Decimal = Field(Decimal("0"), ge=0)


class ProductUpdate(BaseModel):
    sku: str | None = Field(None, min_length=1, max_length=50)
    product_name: str | None = Field(None, min_length=1, max_length=150)
    category_id: int | None = None
    unit_type: Literal["carton", "piece", "both"] | None = None
    pieces_per_carton: int | None = Field(None, ge=1)
    purchase_price: Decimal | None = Field(None, ge=0)
    sale_price: Decimal | None = Field(None, ge=0)
    low_stock_threshold: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    sku: str
    product_name: str
    category_id: int | None
    unit_type: str
    pieces_per_carton: int
    opening_stock: Decimal
    current_stock: Decimal
    purchase_price: Decimal
    stock_value: Decimal
    sale_price: Decimal
    low_stock_threshold: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def current_stock_cartons(self) -> Decimal:
        if self.pieces_per_carton and self.pieces_per_carton > 1:
            return (self.current_stock / Decimal(self.pieces_per_carton)).quantize(Decimal("0.01"))
        return self.current_stock


# ---- Stock ledger ----
class StockLedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_ledger_id: int
    product_id: int
    transaction_type: str
    reference_table: str | None
    reference_id: int | None
    quantity_change: Decimal
    balance_after: Decimal
    created_at: datetime
