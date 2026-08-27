from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BackupLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    backup_id: int
    file_path: str
    backup_type: str
    performed_by: int
    created_at: datetime
    download_url: str | None = None


class RestoreRequest(BaseModel):
    confirm: str  # must equal "RESTORE" to proceed
