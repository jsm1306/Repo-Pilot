"""add Google identity fields to users

Revision ID: 20261102_google_identity
Revises: 076486546208
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261102_google_identity"
down_revision: Union[str, Sequence[str], None] = "076486546208"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("picture_url", sa.String(length=2048), nullable=True))
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=True)
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("users", "picture_url")
    op.drop_column("users", "name")
    op.drop_column("users", "google_sub")
