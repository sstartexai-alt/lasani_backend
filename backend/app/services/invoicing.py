from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase import PurchaseInvoice
from app.models.sales import SalesInvoice


def to_pieces(unit_type: str, quantity: Decimal, pieces_per_carton: int) -> Decimal:
    """Convert a quantity expressed in the given unit into base pieces."""
    if unit_type == "carton":
        return (quantity * Decimal(pieces_per_carton)).quantize(Decimal("0.01"))
    return quantity.quantize(Decimal("0.01"))


async def _next_number(db: AsyncSession, model, number_col, prefix: str) -> str:
    year = date.today().year
    like = f"{prefix}-{year}-%"
    result = await db.execute(
        select(func.max(number_col)).where(number_col.like(like))
    )
    last = result.scalar_one_or_none()
    if last:
        try:
            seq = int(last.rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}-{year}-{seq:06d}"


async def next_sales_invoice_number(db: AsyncSession) -> str:
    return await _next_number(db, SalesInvoice, SalesInvoice.invoice_number, "INV")


async def next_purchase_invoice_number(db: AsyncSession) -> str:
    return await _next_number(db, PurchaseInvoice, PurchaseInvoice.invoice_number, "PUR")
