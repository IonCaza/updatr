import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    os_type: Mapped[str] = mapped_column(String(10), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    winrm_port: Mapped[int] = mapped_column(Integer, default=5986)
    winrm_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    site: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sites.id"), nullable=True
    )
    site_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("hosts.id", ondelete="SET NULL"), nullable=True
    )
    roles: Mapped[list] = mapped_column(JSON, default=list)
    worker_override: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    credential = relationship("Credential", lazy="selectin")
    site_rel = relationship("Site", back_populates="hosts", lazy="selectin")
    parent = relationship(
        "Host",
        remote_side="Host.id",
        foreign_keys="[Host.parent_id]",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list["Host"]] = relationship(
        "Host",
        back_populates="parent",
        foreign_keys="[Host.parent_id]",
        lazy="selectin",
    )
