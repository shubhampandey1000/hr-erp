"""backfill organization_id and enforce not null

Revision ID: b05df17fae8e
Revises: 7b7d8e8b2ca6
Create Date: 2026-09-26 23:41:38.642074

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b05df17fae8e'
down_revision: Union[str, Sequence[str], None] = '7b7d8e8b2ca6'
branch_labels = None
depends_on = None

TABLES = [
    "attendance_records",
    "comp_off_requests",
    "departments",
    "employees",
    "leave_balances",
    "leave_requests",
    "leave_types",
    "payroll_records",
    "salary_structures",
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Find or create a default organization to own pre-multi-tenancy data
    default_org_id = conn.execute(
        sa.text("SELECT id FROM organizations WHERE slug = :slug"),
        {"slug": "default-org"},
    ).scalar()

    if default_org_id is None:
        default_org_id = conn.execute(
            sa.text(
                """
                INSERT INTO organizations (name, slug, subscription_status, created_at, updated_at)
                VALUES (:name, :slug, 'active', now(), now())
                RETURNING id
                """
            ),
            {"name": "Default Organization", "slug": "default-org"},
        ).scalar()

    # 2. Backfill every null organization_id with the default org
    for table in TABLES:
        conn.execute(
            sa.text(f"UPDATE {table} SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": default_org_id},
        )

    # 3. Lock every column down to NOT NULL now that no row is null
    for table in TABLES:
        op.alter_column(table, "organization_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for table in TABLES:
        op.alter_column(table, "organization_id", existing_type=sa.Integer(), nullable=True)
    # Note: rows backfilled into the default organization are intentionally left
    # as-is on downgrade — this only relaxes the constraint, it doesn't undo the 