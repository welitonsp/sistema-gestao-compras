"""Procurement domain ORM models.

These models represent suppliers, products, invoices, and invoice line items for the
institutional procurement system.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    """Trilha de auditoria para operações críticas (Importação, Deleção)."""
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    usuario: Mapped[str] = mapped_column(String(100), index=True)
    operacao: Mapped[str] = mapped_column(String(50))  # ex: "IMPORT_SEFAZ", "IMPORT_XML"
    entidade: Mapped[str] = mapped_column(String(50))  # ex: "NotaFiscal"
    entidade_id: Mapped[str] = mapped_column(String(100)) # Chave de acesso ou UUID
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)


class Fornecedor(TimestampMixin, Base):
    """Represents a supplier that issues invoices to the institution."""

    __tablename__ = "fornecedores"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    cnpj: Mapped[str] = mapped_column(
        String(14),
        unique=True,
        index=True,
        nullable=False,
    )
    razao_social: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    nome_fantasia: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    notas_fiscais: Mapped[list[NotaFiscal]] = relationship(
        back_populates="fornecedor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Produto(TimestampMixin, Base):
    """Canonical product catalog for normalization and price tracking."""

    __tablename__ = "produtos"

    ean: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        doc="Unique identifier (GTIN/EAN) or generated internal code.",
    )
    nome_limpo: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Normalized/Canonical product name.",
    )
    marca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categoria: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    unidade: Mapped[str] = mapped_column(String(20), default="un")

    itens_nota: Mapped[list[ItemNotaFiscal]] = relationship(
        back_populates="produto",
        lazy="selectin",
    )
    historico_precos: Mapped[list[HistoricoPreco]] = relationship(
        back_populates="produto",
        cascade="all, delete-orphan",
        lazy="selectin",
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
    )
    fornecedor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("fornecedores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    numero_nota: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
    )
    chave_acesso: Mapped[str] = mapped_column(
        String(44),
        unique=True,
        index=True,
        nullable=False,
    )
    data_emissao: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
    )

    fornecedor: Mapped[Fornecedor] = relationship(
        back_populates="notas_fiscais",
        lazy="selectin",
    )
    itens: Mapped[list[ItemNotaFiscal]] = relationship(
        back_populates="nota_fiscal",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ItemNotaFiscal(TimestampMixin, Base):
    """Represents a line item extracted from an electronic invoice, linked to a canonical product."""

    __tablename__ = "itens_notas_fiscais"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    nota_fiscal_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("notas_fiscais.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ean: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("produtos.ean", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    descricao_original: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Raw description as found in the invoice.",
    )
    quantidade: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )
    valor_unitario: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=4),
        nullable=False,
    )
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
    )

    nota_fiscal: Mapped[NotaFiscal] = relationship(
        back_populates="itens",
        lazy="selectin",
    )
    produto: Mapped[Produto] = relationship(
        back_populates="itens_nota",
        lazy="selectin",
    )


class HistoricoPreco(TimestampMixin, Base):
    """Consolidated price records for tracking, including manual and fiscal entries."""

    __tablename__ = "historico_precos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ean: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("produtos.ean", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_compra: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    local: Mapped[str] = mapped_column(String(255), nullable=False, doc="Store or supplier name.")
    preco_pago: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=4), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=4), nullable=False)

    produto: Mapped[Produto] = relationship(
        back_populates="historico_precos",
        lazy="selectin",
    )


class ClassificacaoCache(TimestampMixin, Base):
    """Cache for AI classification results to avoid redundant API calls."""

    __tablename__ = "classificacao_cache"

    descricao_original: Mapped[str] = mapped_column(
        String(500),
        primary_key=True,
        doc="Normalized raw description used as cache key.",
    )
    produto_canonico: Mapped[str] = mapped_column(String(255), nullable=False)
    marca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False)
    unidade: Mapped[str] = mapped_column(String(20), default="un")

