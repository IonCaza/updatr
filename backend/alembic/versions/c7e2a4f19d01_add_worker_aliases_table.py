"""add worker_aliases table

Revision ID: c7e2a4f19d01
Revises: b8964073f6cf
Create Date: 2026-02-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7e2a4f19d01"
down_revision: Union[str, Sequence[str], None] = "b8964073f6cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_aliases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("worker_name", sa.String(length=200), unique=True, nullable=False),
        sa.Column("friendly_name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("worker_aliases")
