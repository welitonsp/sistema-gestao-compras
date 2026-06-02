"""Procurement domain ORM models.

These models represent suppliers, products, invoices, and invoice line items for the
institutional procurement system.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint, Text, DateTime, func, Boolean, Integer
import enum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    AUDITOR = "auditor"
    MANAGER = "manager"
    OPERATOR = "operator"

class Department(TimestampMixin, Base):
    """Represents a tenant or institutional department for multi-tenancy."""
    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[list[User]] = relationship(back_populates="department")
    notas_fiscais: Mapped[list[NotaFiscal]] = relationship(back_populates="department")

class User(TimestampMixin, Base):
    """Foundation for Role-Based Access Control (RBAC)."""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.OPERATOR, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    department: Mapped[Department | None] = relationship(back_populates="users")

class AuditLog(TimestampMixin, Base):
    """Trilha de auditoria para operações críticas (Importação, Deleção)."""
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    categoria_confirmada: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categoria_confirmada_por: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categoria_confirmada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    categoria_confirmada_origem: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unidade: Mapped[str] = mapped_column(String(20), default="un")

    itens_nota: Mapped[list[ItemNotaFiscal]] = relationship(
        back_populates="produto",
    )
    historico_precos: Mapped[list[HistoricoPreco]] = relationship(
        back_populates="produto",
        cascade="all, delete-orphan",
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
    department_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        index=True,
    )
    valor_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        server_default="active",
        nullable=False,
        index=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_quality_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_parser_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_item_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_missing_ean_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_empty_description_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_invalid_quantity_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_invalid_value_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_total_itens: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=2), nullable=True)
    extraction_total_nota: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=2), nullable=True)
    extraction_total_mismatch: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extraction_quality_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    department: Mapped[Department | None] = relationship(back_populates="notas_fiscais")
    fornecedor: Mapped[Fornecedor] = relationship(
        back_populates="notas_fiscais",
    )
    itens: Mapped[list[ItemNotaFiscal]] = relationship(
        back_populates="nota_fiscal",
        cascade="all, delete-orphan",
    )
    historico_precos: Mapped[list[HistoricoPreco]] = relationship(
        back_populates="nota_fiscal",
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
    categoria_sugerida: Mapped[str | None] = mapped_column(String(100), nullable=True)
    categoria_sugerida_origem: Mapped[str | None] = mapped_column(String(50), nullable=True)
    categoria_sugerida_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=4),
        nullable=True,
    )
    categoria_sugerida_modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)

    nota_fiscal: Mapped[NotaFiscal] = relationship(
        back_populates="itens",
    )
    produto: Mapped[Produto] = relationship(
        back_populates="itens_nota",
    )
    historico_precos: Mapped[list[HistoricoPreco]] = relationship(
        back_populates="item_nota_fiscal",
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
    nota_fiscal_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("notas_fiscais.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    item_nota_fiscal_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("itens_notas_fiscais.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    data_compra: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    local: Mapped[str] = mapped_column(String(255), nullable=False, doc="Store or supplier name.")
    preco_pago: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=4), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=4), nullable=False)

    produto: Mapped[Produto] = relationship(
        back_populates="historico_precos",
    )
    nota_fiscal: Mapped[NotaFiscal | None] = relationship(
        back_populates="historico_precos",
    )
    item_nota_fiscal: Mapped[ItemNotaFiscal | None] = relationship(
        back_populates="historico_precos",
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
    verificado_usuario: Mapped[bool] = mapped_column(Boolean, default=False)

class Webhook(TimestampMixin, Base):
    """Configuration for external automated notifications."""
    __tablename__ = "webhooks"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    department_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[str] = mapped_column(Text, nullable=False, doc="JSON list of subscribed events")
    secret: Mapped[str | None] = mapped_column(String(255), nullable=True, doc="Secret key for payload signing")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped[Department | None] = relationship()

class APIKey(TimestampMixin, Base):
    """Secure access keys for external system integrations."""
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    department_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, doc="Visible part of the key")
    hashed_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    department: Mapped[Department | None] = relationship()

