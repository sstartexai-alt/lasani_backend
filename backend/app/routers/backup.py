import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Pagination, get_db, require_role
from app.core.security import AppException
from app.models.backup import BackupLog
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.report import BackupLogResponse, RestoreRequest
from app.services.backup import create_backup, restore_backup

router = APIRouter(prefix="/backup", tags=["Backup"])
admin_only = require_role("admin")


def _with_url(log: BackupLog) -> BackupLogResponse:
    resp = BackupLogResponse.model_validate(log)
    resp.download_url = f"/api/v1/backup/{log.backup_id}/download"
    return resp


@router.post("", response_model=BackupLogResponse, status_code=201)
async def run_backup(db: AsyncSession = Depends(get_db), current_user: User = Depends(admin_only)):
    file_path = create_backup()
    log = BackupLog(file_path=file_path, backup_type="manual", performed_by=current_user.user_id)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return _with_url(log)


@router.get("", response_model=Page[BackupLogResponse])
async def list_backups(
    pg: Pagination = Depends(), db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    total = (await db.execute(select(func.count()).select_from(BackupLog))).scalar_one()
    rows = (
        await db.execute(
            select(BackupLog).order_by(BackupLog.backup_id.desc()).limit(pg.limit).offset(pg.offset)
        )
    ).scalars().all()
    return Page.create([_with_url(r) for r in rows], total, pg.page, pg.page_size)


@router.get("/{backup_id}/download")
async def download_backup(
    backup_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    log = await db.get(BackupLog, backup_id)
    if log is None:
        raise AppException(404, "Backup not found", "BACKUP_NOT_FOUND")
    if not os.path.isfile(log.file_path):
        raise AppException(404, "Backup file missing on disk", "BACKUP_FILE_MISSING")
    return FileResponse(log.file_path, media_type="application/sql", filename=os.path.basename(log.file_path))


@router.post("/{backup_id}/restore", response_model=Message)
async def restore(
    backup_id: int,
    payload: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    if payload.confirm != "RESTORE":
        raise AppException(400, "Confirmation failed: 'confirm' must equal 'RESTORE'", "RESTORE_NOT_CONFIRMED")
    log = await db.get(BackupLog, backup_id)
    if log is None:
        raise AppException(404, "Backup not found", "BACKUP_NOT_FOUND")
    restore_backup(log.file_path)
    return Message(detail=f"Database restored from backup #{backup_id}")
