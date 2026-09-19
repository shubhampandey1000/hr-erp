"""add_is_paid_to_leave_types

Revision ID: 1dce892dbe18
Revises: 93e58176ef7e
Create Date: 2026-09-19 17:11:09.104145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1dce892dbe18'
down_revision: Union[str, Sequence[str], None] = '93e58176ef7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_types",
        sa.Column("is_paid", sa.Boolean(), server_default=sa.text("true"), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("leave_types", "is_paid")
