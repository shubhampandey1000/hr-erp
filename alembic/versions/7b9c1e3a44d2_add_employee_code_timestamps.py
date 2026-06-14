"""add employee_code and timestamps to employees

Revision ID: 7b9c1e3a44d2
Revises: 4b84daf98d83
Create Date: 2026-06-14 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b9c1e3a44d2'
down_revision: Union[str, Sequence[str], None] = '4b84daf98d83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'employees',
        sa.Column('employee_code', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'employees',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column(
        'employees',
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.execute(
        "UPDATE employees SET employee_code = concat('EMP', lpad(id::text, 8, '0')) WHERE employee_code IS NULL;"
    )
    op.execute("UPDATE employees SET role = 'employee' WHERE role IS NULL;")
    op.execute("UPDATE employees SET is_active = true WHERE is_active IS NULL;")

    op.create_index(
        op.f('ix_employees_employee_code'),
        'employees',
        ['employee_code'],
        unique=True,
    )

    op.alter_column(
        'employees',
        'employee_code',
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.alter_column(
        'employees',
        'is_active',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text('true'),
    )
    op.alter_column(
        'employees',
        'role',
        existing_type=sa.String(length=50),
        nullable=False,
        server_default=sa.text("'employee'"),
    )


def downgrade() -> None:
    op.alter_column(
        'employees',
        'role',
        existing_type=sa.String(length=50),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        'employees',
        'is_active',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    op.drop_index(op.f('ix_employees_employee_code'), table_name='employees')
    op.drop_column('employees', 'updated_at')
    op.drop_column('employees', 'created_at')
    op.drop_column('employees', 'employee_code')
