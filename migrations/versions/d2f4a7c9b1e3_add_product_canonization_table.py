"""Add product canonization mapping table

Revision ID: d2f4a7c9b1e3
Revises: b7e4c9a2d1f0
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2f4a7c9b1e3"
down_revision: Union[str, Sequence[str], None] = "b7e4c9a2d1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "canonizacoes_produtos",
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("ean_original", sa.String(length=32), nullable=False),
        sa.Column("ean_canonico", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confirmado_por", sa.String(length=100), nullable=True),
        sa.Column("confirmado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'reverted')",
            name="ck_canonizacoes_produtos_status",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_canonizacoes_produtos_confidence_score",
        ),
        sa.CheckConstraint(
            "ean_original <> ean_canonico",
            name="ck_canonizacoes_produtos_eans_distintos",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ean_original"],
            ["produtos.ean"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ean_canonico"],
            ["produtos.ean"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("department_id", "ean_original"),
    )
    op.create_index(
        "ix_canonizacoes_produtos_department_id",
        "canonizacoes_produtos",
        ["department_id"],
        unique=False,
    )
    op.create_index(
        "ix_canonizacoes_produtos_ean_canonico",
        "canonizacoes_produtos",
        ["ean_canonico"],
        unique=False,
    )
    op.create_index(
        "ix_canonizacoes_produtos_department_id_ean_canonico",
        "canonizacoes_produtos",
        ["department_id", "ean_canonico"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_canonizacoes_produtos_department_id_ean_canonico",
        table_name="canonizacoes_produtos",
    )
    op.drop_index(
        "ix_canonizacoes_produtos_ean_canonico",
        table_name="canonizacoes_produtos",
    )
    op.drop_index(
        "ix_canonizacoes_produtos_department_id",
        table_name="canonizacoes_produtos",
    )
    op.drop_table("canonizacoes_produtos")
