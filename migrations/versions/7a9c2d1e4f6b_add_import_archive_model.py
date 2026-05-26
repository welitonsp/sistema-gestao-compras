"""Add import archive model

Revision ID: 7a9c2d1e4f6b
Revises: 653a6d6ddaa7
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a9c2d1e4f6b"
down_revision: Union[str, Sequence[str], None] = "653a6d6ddaa7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "notas_fiscais",
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.add_column("notas_fiscais", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notas_fiscais", sa.Column("archived_by", sa.String(length=100), nullable=True))
    op.add_column("notas_fiscais", sa.Column("archive_reason", sa.Text(), nullable=True))
    op.create_index(op.f("ix_notas_fiscais_status"), "notas_fiscais", ["status"], unique=False)

    op.add_column("historico_precos", sa.Column("nota_fiscal_id", sa.UUID(), nullable=True))
    op.add_column("historico_precos", sa.Column("item_nota_fiscal_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_historico_precos_nota_fiscal_id"),
        "historico_precos",
        ["nota_fiscal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_historico_precos_item_nota_fiscal_id"),
        "historico_precos",
        ["item_nota_fiscal_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_historico_precos_nota_fiscal_id",
        "historico_precos",
        "notas_fiscais",
        ["nota_fiscal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_historico_precos_item_nota_fiscal_id",
        "historico_precos",
        "itens_notas_fiscais",
        ["item_nota_fiscal_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_historico_precos_item_nota_fiscal_id", "historico_precos", type_="foreignkey")
    op.drop_constraint("fk_historico_precos_nota_fiscal_id", "historico_precos", type_="foreignkey")
    op.drop_index(op.f("ix_historico_precos_item_nota_fiscal_id"), table_name="historico_precos")
    op.drop_index(op.f("ix_historico_precos_nota_fiscal_id"), table_name="historico_precos")
    op.drop_column("historico_precos", "item_nota_fiscal_id")
    op.drop_column("historico_precos", "nota_fiscal_id")

    op.drop_index(op.f("ix_notas_fiscais_status"), table_name="notas_fiscais")
    op.drop_column("notas_fiscais", "archive_reason")
    op.drop_column("notas_fiscais", "archived_by")
    op.drop_column("notas_fiscais", "archived_at")
    op.drop_column("notas_fiscais", "status")
