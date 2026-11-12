"""add collection_item.print_subtitle

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable, with no default: an item has no subtitle until one is typed in.
    op.add_column(
        "collection_item",
        sa.Column("print_subtitle", sa.String(length=100), nullable=True),
    )


def downgrade():
    op.drop_column("collection_item", "print_subtitle")
