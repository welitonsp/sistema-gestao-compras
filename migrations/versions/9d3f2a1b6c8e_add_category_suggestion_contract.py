"""Add category suggestion and confirmation contract

Revision ID: 9d3f2a1b6c8e
Revises: 7a9c2d1e4f6b
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3f2a1b6c8e"
down_revision: Union[str, Sequence[str], None] = "7a9c2d1e4f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("itens_notas_fiscais", sa.Column("categoria_sugerida", sa.String(length=100), nullable=True))
    op.add_column("itens_notas_fiscais", sa.Column("categoria_sugerida_origem", sa.String(length=50), nullable=True))
    op.add_column(
        "itens_notas_fiscais",
        sa.Column("categoria_sugerida_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
    )
    op.add_column("itens_notas_fiscais", sa.Column("categoria_sugerida_modelo", sa.String(length=100), nullable=True))

    op.add_column("produtos", sa.Column("categoria_confirmada", sa.String(length=100), nullable=True))
    op.add_column("produtos", sa.Column("categoria_confirmada_por", sa.String(length=100), nullable=True))
    op.add_column("produtos", sa.Column("categoria_confirmada_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("produtos", sa.Column("categoria_confirmada_origem", sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("produtos", "categoria_confirmada_origem")
    op.drop_column("produtos", "categoria_confirmada_em")
    op.drop_column("produtos", "categoria_confirmada_por")
    op.drop_column("produtos", "categoria_confirmada")

    op.drop_column("itens_notas_fiscais", "categoria_sugerida_modelo")
    op.drop_column("itens_notas_fiscais", "categoria_sugerida_confidence")
    op.drop_column("itens_notas_fiscais", "categoria_sugerida_origem")
    op.drop_column("itens_notas_fiscais", "categoria_sugerida")
