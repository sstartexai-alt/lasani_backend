import os
import subprocess
from datetime import datetime

from app.core.config import settings
from app.core.security import AppException


def _ensure_backup_dir() -> str:
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)
    return settings.BACKUP_DIR


def create_backup() -> str:
    """Run mysqldump and return the absolute path to the generated .sql file."""
    backup_dir = _ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{settings.DB_NAME}_{timestamp}.sql"
    file_path = os.path.abspath(os.path.join(backup_dir, filename))

    cmd = [
        settings.MYSQLDUMP_PATH,
        f"-h{settings.DB_HOST}",
        f"-P{settings.DB_PORT}",
        f"-u{settings.DB_USER}",
        f"-p{settings.DB_PASSWORD}",
        "--routines",
        "--triggers",
        "--single-transaction",
        settings.DB_NAME,
    ]
    try:
        with open(file_path, "wb") as out:
            proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, timeout=600)
    except FileNotFoundError:
        raise AppException(500, f"mysqldump not found at '{settings.MYSQLDUMP_PATH}'", "BACKUP_TOOL_MISSING")
    except subprocess.TimeoutExpired:
        raise AppException(500, "Backup timed out", "BACKUP_TIMEOUT")

    if proc.returncode != 0:
        raise AppException(500, f"mysqldump failed: {proc.stderr.decode(errors='ignore')}", "BACKUP_FAILED")
    return file_path


def restore_backup(file_path: str) -> None:
    if not os.path.isfile(file_path):
        raise AppException(404, "Backup file not found on disk", "BACKUP_FILE_MISSING")

    cmd = [
        settings.MYSQL_PATH,
        f"-h{settings.DB_HOST}",
        f"-P{settings.DB_PORT}",
        f"-u{settings.DB_USER}",
        f"-p{settings.DB_PASSWORD}",
        settings.DB_NAME,
    ]
    try:
        with open(file_path, "rb") as src:
            proc = subprocess.run(cmd, stdin=src, stderr=subprocess.PIPE, timeout=600)
    except FileNotFoundError:
        raise AppException(500, f"mysql client not found at '{settings.MYSQL_PATH}'", "RESTORE_TOOL_MISSING")
    except subprocess.TimeoutExpired:
        raise AppException(500, "Restore timed out", "RESTORE_TIMEOUT")

    if proc.returncode != 0:
        raise AppException(500, f"restore failed: {proc.stderr.decode(errors='ignore')}", "RESTORE_FAILED")
