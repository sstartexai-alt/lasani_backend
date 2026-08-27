from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BackupLog(Base):
    __tablename__ = "backup_logs"

    backup_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    backup_type: Mapped[str] = mapped_column(
        Enum("manual", "automatic", name="backup_type"), nullable=False, default="manual"
    )
    performed_by: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.current_timestamp())
