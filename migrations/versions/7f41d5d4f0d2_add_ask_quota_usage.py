"""add ask quota usage

Revision ID: 7f41d5d4f0d2
Revises: 0f6331267571
Create Date: 2026-05-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "7f41d5d4f0d2"
down_revision = "0f6331267571"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ask_quota_usage",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("ask_quota_usage")
