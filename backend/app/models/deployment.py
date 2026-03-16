import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, Text, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RegistryConfig(Base):
    __tablename__ = "registry_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, default="updatr")
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    build_host_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hosts.id"), nullable=False
    )
    repo_path: Mapped[str] = mapped_column(String(500), nullable=False, default="/opt/updatr")
    external_database_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_redis_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    build_host = relationship("Host", lazy="selectin")


class ImageBuild(Base):
    __tablename__ = "image_builds"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    registry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registry_configs.id"), nullable=False
    )
    image_tag: Mapped[str] = mapped_column(String(200), nullable=False)
    git_ref: Mapped[str] = mapped_column(String(200), nullable=False, default="main")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    build_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    registry = relationship("RegistryConfig", lazy="selectin")


class WorkerDeployment(Base):
    __tablename__ = "worker_deployments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    host_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hosts.id"), nullable=False
    )
    registry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("registry_configs.id"), nullable=False
    )
    image_tag: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    worker_site: Mapped[str] = mapped_column(String(100), nullable=False)
    env_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    host = relationship("Host", lazy="selectin")
    registry = relationship("RegistryConfig", lazy="selectin")
