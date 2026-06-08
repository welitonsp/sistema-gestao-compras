"""Make classification cache tenant-aware

Revision ID: 73d1e0a4c9b2
Revises: 5b9e1f0c2a3d
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "73d1e0a4c9b2"
down_revision: Union[str, Sequence[str], None] = "5b9e1f0c2a3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "classificacao_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "classificacao_cache",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT descricao_original FROM classificacao_cache")).fetchall()
    for row in rows:
        bind.execute(
            sa.text(
                "UPDATE classificacao_cache SET id = :id "
                "WHERE descricao_original = :descricao_original"
            ),
            {"id": str(uuid4()), "descricao_original": row.descricao_original},
        )

    with op.batch_alter_table("classificacao_cache") as batch_op:
        batch_op.drop_constraint("classificacao_cache_pkey", type_="primary")
        batch_op.alter_column("id", nullable=False)
        batch_op.create_primary_key("classificacao_cache_pkey", ["id"])
        batch_op.create_foreign_key(
            "fk_classificacao_cache_department_id",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_index(
        "ix_classificacao_cache_department_id",
        "classificacao_cache",
        ["department_id"],
    )
    op.create_index(
        "ix_classificacao_cache_descricao_original",
        "classificacao_cache",
        ["descricao_original"],
    )
    op.create_index(
        "ix_classificacao_cache_department_descricao",
        "classificacao_cache",
        ["department_id", "descricao_original"],
    )
    op.create_index(
        "uq_classificacao_cache_global_descricao",
        "classificacao_cache",
        ["descricao_original"],
        unique=True,
        postgresql_where=sa.text("department_id IS NULL"),
        sqlite_where=sa.text("department_id IS NULL"),
    )
    op.create_index(
        "uq_classificacao_cache_department_descricao",
        "classificacao_cache",
        ["department_id", "descricao_original"],
        unique=True,
        postgresql_where=sa.text("department_id IS NOT NULL"),
        sqlite_where=sa.text("department_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_classificacao_cache_department_descricao", table_name="classificacao_cache")
    op.drop_index("uq_classificacao_cache_global_descricao", table_name="classificacao_cache")
    op.drop_index("ix_classificacao_cache_department_descricao", table_name="classificacao_cache")
    op.drop_index("ix_classificacao_cache_descricao_original", table_name="classificacao_cache")
    op.drop_index("ix_classificacao_cache_department_id", table_name="classificacao_cache")

    op.execute("DELETE FROM classificacao_cache WHERE department_id IS NOT NULL")

    with op.batch_alter_table("classificacao_cache") as batch_op:
        batch_op.drop_constraint("fk_classificacao_cache_department_id", type_="foreignkey")
        batch_op.drop_constraint("classificacao_cache_pkey", type_="primary")
        batch_op.create_primary_key("classificacao_cache_pkey", ["descricao_original"])

    op.drop_column("classificacao_cache", "department_id")
    op.drop_column("classificacao_cache", "id")
