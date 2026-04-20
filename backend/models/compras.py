"""Procurement domain ORM models.

These models represent suppliers, invoices, and invoice line items for the
institutional procurement system.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Fornecedor(TimestampMixin, Base):
    """Represents a supplier that issues invoices to the institution."""

    __tablename__ = "fornecedores"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
        doc="Primary identifier for the supplier.",
    )
    cnpj: Mapped[str] = mapped_column(
        String(14),
        unique=True,
        index=True,
        nullable=False,
        doc="Supplier CNPJ stored without formatting punctuation.",
    )
    razao_social: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Registered legal name of the supplier.",
    )
    nome_fantasia: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Trade name of the supplier when available.",
    )

    notas_fiscais: Mapped[list[NotaFiscal]] = relationship(
        back_populates="fornecedor",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="NotaFiscal.data_emissao.desc()",
    )


class NotaFiscal(TimestampMixin, Base):
    """Represents an electronic invoice associated with a supplier."""

    __tablename__ = "notas_fiscais"
    __table_args__ = (
        UniqueConstraint("chave_acesso", name="uq_notas_fiscais_chave_acesso"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
        doc="Primary identifier for the invoice.",
    )
    fornecedor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("fornecedores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Reference to the supplier that issued the invoice.",
    )
    numero_nota: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        doc="Invoice number as provided by the fiscal document.",
    )
    chave_acesso: Mapped[str] = mapped_column(
        String(44),
        unique=True,
        index=True,
        nullable=False,
        doc="Unique fiscal access key used to identify XML and PDF documents.",
    )
    data_emissao: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Invoice issue date.",
    )
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
        doc="Total invoice amount.",
    )

    fornecedor: Mapped[Fornecedor] = relationship(
        back_populates="notas_fiscais",
        lazy="selectin",
    )
    itens: Mapped[list[ItemNotaFiscal]] = relationship(
        back_populates="nota_fiscal",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ItemNotaFiscal.descricao.asc()",
    )


class ItemNotaFiscal(TimestampMixin, Base):
    """Represents a line item extracted from an electronic invoice."""

    __tablename__ = "itens_notas_fiscais"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
        doc="Primary identifier for the invoice line item.",
    )
    nota_fiscal_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("notas_fiscais.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to the invoice that owns this line item.",
    )
    codigo_produto: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Supplier product code extracted from the invoice XML.",
    )
    descricao: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Textual description of the purchased item.",
    )
    quantidade: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
        doc="Purchased quantity of the item.",
    )
    valor_unitario: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
        doc="Unit price of the item.",
    )
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
        doc="Total line amount for the item.",
    )

    nota_fiscal: Mapped[NotaFiscal] = relationship(
        back_populates="itens",
        lazy="selectin",
    )
