"""add deployment tables (registry_configs, image_builds, worker_deployments)

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-02-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registry_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), unique=True, nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("project", sa.String(length=100), nullable=False, server_default="updatr"),
        sa.Column("username", sa.String(length=200), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column(
            "build_host_id",
            sa.String(length=36),
            sa.ForeignKey("hosts.id"),
            nullable=False,
        ),
        sa.Column("repo_path", sa.String(length=500), nullable=False, server_default="/opt/updatr"),
        sa.Column("external_database_url", sa.String(length=500), nullable=True),
        sa.Column("external_redis_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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

    op.create_table(
        "image_builds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "registry_id",
            sa.String(length=36),
            sa.ForeignKey("registry_configs.id"),
            nullable=False,
        ),
        sa.Column("image_tag", sa.String(length=200), nullable=False),
        sa.Column("git_ref", sa.String(length=200), nullable=False, server_default="main"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("build_log", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "worker_deployments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "host_id",
            sa.String(length=36),
            sa.ForeignKey("hosts.id"),
            nullable=False,
        ),
        sa.Column(
            "registry_id",
            sa.String(length=36),
            sa.ForeignKey("registry_configs.id"),
            nullable=False,
        ),
        sa.Column("image_tag", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("worker_site", sa.String(length=100), nullable=False),
        sa.Column("env_snapshot", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("worker_deployments")
    op.drop_table("image_builds")
    op.drop_table("registry_configs")
