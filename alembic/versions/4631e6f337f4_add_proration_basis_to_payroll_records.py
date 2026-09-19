"""add_proration_basis_to_payroll_records

Revision ID: 4631e6f337f4
Revises: 1dce892dbe18
Create Date: 2026-09-19 17:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4631e6f337f4'
down_revision: Union[str, Sequence[str], None] = '1dce892dbe18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payroll_records",
        sa.Column(
            "proration_basis",
            sa.String(length=50),
            server_default="calendar_days",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("payroll_records", "proration_basis")