"""add site column to hosts

Revision ID: b8964073f6cf
Revises: 
Create Date: 2026-02-21 14:48:06.211057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8964073f6cf'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'hosts',
        sa.Column('site', sa.String(length=50), nullable=False, server_default='default'),
    )
    op.add_column(
        'hosts',
        sa.Column('is_self', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'hosts',
        sa.Column('worker_override', sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('hosts', 'worker_override')
    op.drop_column('hosts', 'is_self')
    op.drop_column('hosts', 'site')
