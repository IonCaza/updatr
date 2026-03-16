"""add sites table and host hierarchy columns

Revision ID: e5f6a7b8c9d0
Revises: d4f1b2e83a09
Create Date: 2026-02-20 18:00:00.000000

"""
from typing import Sequence, Union

import uuid
from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4f1b2e83a09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sites_table = op.create_table(
        "sites",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("subnets", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
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

    op.add_column(
        "hosts",
        sa.Column("site_id", sa.String(length=36), sa.ForeignKey("sites.id"), nullable=True),
    )
    op.add_column(
        "hosts",
        sa.Column("site_locked", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "hosts",
        sa.Column(
            "parent_id",
            sa.String(length=36),
            sa.ForeignKey("hosts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "hosts",
        sa.Column("roles", sa.JSON(), server_default="[]", nullable=False),
    )

    conn = op.get_bind()

    # Collect distinct site names from hosts
    existing_sites = conn.execute(
        sa.text("SELECT DISTINCT site FROM hosts WHERE site IS NOT NULL")
    ).fetchall()
    site_names = {row[0] for row in existing_sites}
    site_names.add("default")

    # Create a Site row for each distinct value
    site_map = {}
    for name in sorted(site_names):
        site_id = str(uuid.uuid4())
        site_map[name] = site_id
        is_default = name == "default"
        conn.execute(
            sites_table.insert().values(
                id=site_id,
                name=name,
                display_name=name.replace("-", " ").replace("_", " ").title(),
                description=None,
                subnets=[],
                is_default=is_default,
            )
        )

    # Populate hosts.site_id from the legacy site string
    for name, site_id in site_map.items():
        conn.execute(
            sa.text("UPDATE hosts SET site_id = :sid WHERE site = :sname"),
            {"sid": site_id, "sname": name},
        )

    # Migrate is_self=True to roles=["worker"]
    conn.execute(
        sa.text("""UPDATE hosts SET roles = '["worker"]' WHERE is_self = true""")
    )


def downgrade() -> None:
    op.drop_column("hosts", "roles")
    op.drop_column("hosts", "parent_id")
    op.drop_column("hosts", "site_locked")
    op.drop_column("hosts", "site_id")
    op.drop_table("sites")
