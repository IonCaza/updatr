import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComplianceScan(Base):
    __tablename__ = "compliance_scans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    host_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hosts.id"), nullable=False
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_updates: Mapped[list] = mapped_column(JSON, default=list)
    reboot_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reachable: Mapped[bool] = mapped_column(Boolean, default=True)
    worker_queue: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_log: Mapped[list] = mapped_column(JSON, default=list)
