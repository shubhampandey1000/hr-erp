"""add_unique_constraint_to_salary_structure_employee_id

Revision ID: 93e58176ef7e
Revises: cf24005732de
Create Date: 2026-09-19 17:01:51.752218

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '93e58176ef7e'
down_revision: str | Sequence[str] | None = 'cf24005732de'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_salary_structures_employee_id",
        "salary_structures",
        ["employee_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_salary_structures_employee_id",
        "salary_structures",
        type_="unique"
    )