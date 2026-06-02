"""Add index to notas fiscais data emissao

Revision ID: b7e4c9a2d1f0
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7e4c9a2d1f0"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_notas_fiscais_data_emissao",
        "notas_fiscais",
        ["data_emissao"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_notas_fiscais_data_emissao",
        table_name="notas_fiscais",
    )
