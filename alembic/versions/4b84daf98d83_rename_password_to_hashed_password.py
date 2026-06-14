"""rename password to hashed_password

Revision ID: 4b84daf98d83
Revises: dba466600e68
Create Date: 2026-06-14 21:30:20.725361

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b84daf98d83'
down_revision: Union[str, Sequence[str], None] = 'dba466600e68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "employees",
        "password",
        new_column_name="hashed_password"
    )


def downgrade():
    op.alter_column(
        "employees",
        "hashed_password",
        new_column_name="password"
    )
