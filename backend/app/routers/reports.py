from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.utils.csv_export import rows_to_csv_response

router = APIRouter(prefix="/reports", tags=["Reports"])
admin_only = require_role("admin")


def _serialize(rows) -> list[dict]:
    out = []
    for row in rows:
        d = dict(row._mapping)
        for key, value in d.items():
            if isinstance(value, Decimal):
                d[key] = float(value)
            elif isinstance(value, date):
                d[key] = value.isoformat()
        out.append(d)
    return out


async def _run(db: AsyncSession, sql, params: dict | None = None):
    result = await db.execute(text(sql) if isinstance(sql, str) else sql, params or {})
    return _serialize(result.fetchall())


def _respond(rows: list[dict], fmt: str, filename: str):
    if fmt == "csv":
        return rows_to_csv_response(rows, filename)
    return rows


@router.get("/today-sales")
async def today_sales(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_today_sales")
    return _respond(rows, fmt, "today_sales.csv")


@router.get("/monthly-sales")
async def monthly_sales(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM"),
    fmt: str = Query("json", alias="format"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    if month:
        rows = await _run(
            db, "SELECT * FROM vw_monthly_sales WHERE sales_month = :month", {"month": month}
        )
    else:
        rows = await _run(db, "SELECT * FROM vw_monthly_sales ORDER BY sales_month DESC")
    return _respond(rows, fmt, "monthly_sales.csv")


@router.get("/customer-wise-sales")
async def customer_wise_sales(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_customer_wise_sales ORDER BY total_sales DESC")
    return _respond(rows, fmt, "customer_wise_sales.csv")


@router.get("/product-wise-sales")
async def product_wise_sales(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_product_wise_sales ORDER BY total_sales_amount DESC")
    return _respond(rows, fmt, "product_wise_sales.csv")


@router.get("/outstanding-customers")
async def outstanding_customers(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_outstanding_customers ORDER BY current_balance DESC")
    return _respond(rows, fmt, "outstanding_customers.csv")


@router.get("/stock")
async def stock_report(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_stock_report ORDER BY product_name")
    return _respond(rows, fmt, "stock_report.csv")


@router.get("/purchases")
async def purchase_report(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_purchase_report ORDER BY purchase_date DESC")
    return _respond(rows, fmt, "purchase_report.csv")


@router.get("/profit")
async def profit_report(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    fmt: str = Query("json", alias="format"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    clauses, params = [], {}
    if date_from:
        clauses.append("invoice_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        clauses.append("invoice_date <= :date_to")
        params["date_to"] = date_to
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = await _run(db, f"SELECT * FROM vw_profit_report{where} ORDER BY invoice_date DESC", params)
    return _respond(rows, fmt, "profit_report.csv")


@router.get("/cash-summary")
async def cash_summary(fmt: str = Query("json", alias="format"), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    rows = await _run(db, "SELECT * FROM vw_cash_summary")
    return _respond(rows, fmt, "cash_summary.csv")
