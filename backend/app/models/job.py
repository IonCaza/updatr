import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    host_ids: Mapped[list] = mapped_column(JSON, default=list)
    tags_filter: Mapped[list] = mapped_column(JSON, default=list)
    patch_categories: Mapped[list] = mapped_column(JSON, default=list)
    reboot_policy: Mapped[str] = mapped_column(String(20), default="if-required")
    schedule_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schedules.id"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    host_results: Mapped[dict] = mapped_column(JSON, default=dict)
    wave_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    current_wave: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    events = relationship("JobEvent", back_populates="job", lazy="selectin")


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id"), nullable=False
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    task_name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    job = relationship("Job", back_populates="events")
