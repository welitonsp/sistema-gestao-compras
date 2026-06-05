"""Add canonization revert tracking fields

Revision ID: 5b9e1f0c2a3d
Revises: d2f4a7c9b1e3
Create Date: 2026-06-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b9e1f0c2a3d"
down_revision: Union[str, Sequence[str], None] = "d2f4a7c9b1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "canonizacoes_produtos",
        sa.Column("revertido_por", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "canonizacoes_produtos",
        sa.Column("revertido_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonizacoes_produtos",
        sa.Column("revert_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("canonizacoes_produtos", "revert_reason")
    op.drop_column("canonizacoes_produtos", "revertido_em")
    op.drop_column("canonizacoes_produtos", "revertido_por")
