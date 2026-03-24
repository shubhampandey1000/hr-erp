"""make password not null

Revision ID: b64bb84de055
Revises: a9a54071ee52
Create Date: 2026-03-22 14:04:52.701549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b64bb84de055'
down_revision: Union[str, Sequence[str], None] = 'a9a54071ee52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
