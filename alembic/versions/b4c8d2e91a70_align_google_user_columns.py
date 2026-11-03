"""Align user identity columns with the Google-auth ORM model.

Revision ID: b4c8d2e91a70
Revises: 076486546208
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b4c8d2e91a70"
down_revision: Union[str, Sequence[str], None] = "076486546208"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("picture_url", sa.String(length=2048), nullable=True))
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_column("users", "picture_url")
    op.drop_column("users", "name")
    op.drop_column("users", "google_sub")
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=False,
    )
