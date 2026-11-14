"""Panel operators with local password hashes and roles.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "operators" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "operators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("disabled", sa.Boolean, nullable=False),
        sa.Column("token_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_operators_username", "operators", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_operators_username", table_name="operators")
    op.drop_table("operators")
