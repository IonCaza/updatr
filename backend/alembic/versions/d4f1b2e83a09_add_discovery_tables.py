"""add discovery tables

Revision ID: d4f1b2e83a09
Revises: c7e2a4f19d01
Create Date: 2026-02-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4f1b2e83a09"
down_revision: Union[str, Sequence[str], None] = "c7e2a4f19d01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovery_scans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column("depth", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("host_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "discovered_hosts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "scan_id",
            sa.String(length=36),
            sa.ForeignKey("discovery_scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("os_guess", sa.String(length=200), nullable=True),
        sa.Column("os_type", sa.String(length=20), server_default="unknown", nullable=False),
        sa.Column("os_confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("open_ports", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("imported", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("discovered_hosts")
    op.drop_table("discovery_scans")
