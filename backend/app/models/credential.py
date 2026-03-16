import uuid
from datetime import datetime, timezone

from sqlalchemy import String, LargeBinary, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    encrypted_password: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    encrypted_private_key: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    encrypted_passphrase: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
