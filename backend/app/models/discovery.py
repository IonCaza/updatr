import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiscoveryScan(Base):
    __tablename__ = "discovery_scans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    depth: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    host_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    hosts: Mapped[list["DiscoveredHost"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", lazy="selectin"
    )


class DiscoveredHost(Base):
    __tablename__ = "discovered_hosts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_scans.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_guess: Mapped[str | None] = mapped_column(String(200), nullable=True)
    os_type: Mapped[str] = mapped_column(String(20), default="unknown")
    os_confidence: Mapped[int] = mapped_column(Integer, default=0)
    open_ports: Mapped[list] = mapped_column(JSON, default=list)
    imported: Mapped[bool] = mapped_column(Boolean, default=False)

    scan: Mapped["DiscoveryScan"] = relationship(back_populates="hosts")
