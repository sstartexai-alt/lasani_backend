from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
admin_only = require_role("admin")


@router.get("/summary")
async def dashboard_summary(db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    result = await db.execute(text("SELECT * FROM vw_dashboard_summary"))
    row = result.fetchone()
    if row is None:
        return {}
    data = dict(row._mapping)
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in data.items()}
