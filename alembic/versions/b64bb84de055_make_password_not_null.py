"""make password not null

Revision ID: b64bb84de055
Revises: a9a54071ee52
Create Date: 2026-03-22 14:04:52.701549

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'b64bb84de055'
down_revision: str | Sequence[str] | None = 'a9a54071ee52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
