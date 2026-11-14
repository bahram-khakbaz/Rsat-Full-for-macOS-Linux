"""Baseline schema.

Creates every table that existed before migrations were introduced, skipping
tables that are already present so earlier installations are adopted in place.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _device_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password", sa.Text, nullable=False),
        sa.Column("fingerprint", sa.String(100), nullable=False),
    ]


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    def create(name: str, columns: list, indexes: list[tuple[str, bool]]) -> None:
        if name in existing:
            return
        op.create_table(name, *columns)
        for column, unique in indexes:
            op.create_index(f"ix_{name}_{column}", name, [column], unique=unique)

    create(
        "audit_logs",
        [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor", sa.String(255), nullable=False),
            sa.Column("role", sa.String(50), nullable=False),
            sa.Column("action", sa.String(120), nullable=False),
            sa.Column("target", sa.String(255), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("details", sa.Text, nullable=False),
        ],
        [("at", False), ("actor", False), ("action", False)],
    )
    create(
        "system_settings",
        [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("key", sa.String(120), nullable=False),
            sa.Column("value", sa.Text, nullable=False),
        ],
        [("key", True)],
    )
    create(
        "site_configs",
        [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("description", sa.Text, nullable=False),
        ],
        [("name", True)],
    )
    create(
        "domain_controller_configs",
        [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "site_id",
                sa.Integer,
                sa.ForeignKey("site_configs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("host", sa.String(255), nullable=False),
            sa.Column("ip", sa.String(64), nullable=False),
            sa.Column("enabled", sa.Boolean, nullable=False),
            sa.Column("notes", sa.Text, nullable=False),
        ],
        [("site_id", False), ("host", False)],
    )
    create("ssh_switches", _device_columns(), [("owner", False)])
    create(
        "ipam_vlans",
        [
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("owner", sa.String(255), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("cidr", sa.String(32), nullable=False),
            sa.Column("default_status", sa.String(16), nullable=False),
            sa.Column("states", sa.Text, nullable=False),
            sa.Column("revision", sa.Integer, nullable=False),
        ],
        [("owner", False)],
    )
    create("ssh_linux_servers", _device_columns(), [("owner", False)])


def downgrade() -> None:
    # The baseline adopts pre-existing data; dropping it would destroy an installation.
    raise RuntimeError("The baseline revision cannot be downgraded")
