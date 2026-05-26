"""Add extraction quality fields to notas fiscais

Revision ID: a1b2c3d4e5f6
Revises: 9d3f2a1b6c8e
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9d3f2a1b6c8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("notas_fiscais", sa.Column("extraction_quality_status", sa.String(length=20), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_parser_source", sa.String(length=20), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_item_count", sa.Integer(), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_missing_ean_count", sa.Integer(), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_empty_description_count", sa.Integer(), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_invalid_quantity_count", sa.Integer(), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_invalid_value_count", sa.Integer(), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_total_itens", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_total_nota", sa.Numeric(precision=14, scale=2), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_total_mismatch", sa.Boolean(), nullable=True))
    op.add_column("notas_fiscais", sa.Column("extraction_quality_details", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("notas_fiscais", "extraction_quality_details")
    op.drop_column("notas_fiscais", "extraction_total_mismatch")
    op.drop_column("notas_fiscais", "extraction_total_nota")
    op.drop_column("notas_fiscais", "extraction_total_itens")
    op.drop_column("notas_fiscais", "extraction_invalid_value_count")
    op.drop_column("notas_fiscais", "extraction_invalid_quantity_count")
    op.drop_column("notas_fiscais", "extraction_empty_description_count")
    op.drop_column("notas_fiscais", "extraction_missing_ean_count")
    op.drop_column("notas_fiscais", "extraction_item_count")
    op.drop_column("notas_fiscais", "extraction_parser_source")
    op.drop_column("notas_fiscais", "extraction_quality_status")
