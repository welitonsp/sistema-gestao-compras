"""Transactional product canonization confirmation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import AuditLog, CanonizacaoProduto, Department, Produto


ACTIVE_STATUS = "active"
PRODUCT_CANONIZED_OPERATION = "PRODUCT_CANONIZED"
MAX_ORIGINAL_EANS = 50
MAX_REASON_LENGTH = 500


class ProductCanonizationError(Exception):
    """Base error for controlled product canonization failures."""


class ProductCanonizationValidationError(ProductCanonizationError):
    """Raised when the confirmation payload is invalid."""


class ProductCanonizationNotFoundError(ProductCanonizationError):
    """Raised when a referenced department or product does not exist."""


class ProductCanonizationConflictError(ProductCanonizationError):
    """Raised when an active or ambiguous mapping already exists."""


@dataclass(frozen=True)
class CanonizationCreatedMapping:
    ean_original: str
    ean_canonico: str
    status: str


@dataclass(frozen=True)
class CanonizationConfirmationResult:
    ean_canonico: str
    department_id: UUID
    created_mappings: list[CanonizationCreatedMapping]

    @property
    def created_count(self) -> int:
        return len(self.created_mappings)

    @property
    def summary(self) -> str:
        return f"{self.created_count} mapeamento(s) de canonizacao criado(s)."


class ProductCanonizationService:
    """Creates logical product canonization mappings without changing fiscal data."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def confirm_canonization(
        self,
        *,
        ean_canonico: str,
        eans_originais: list[str],
        department_id: UUID,
        usuario_executor: str,
        reason: str | None = None,
    ) -> CanonizationConfirmationResult:
        """Confirm mappings in a single transaction and roll back on any failure."""

        try:
            safe_reason = _sanitize_reason(reason)
            safe_usuario = _sanitize_usuario(usuario_executor)
            canonical = _sanitize_ean(ean_canonico, "ean_canonico")
            originals = _sanitize_original_eans(eans_originais)

            if canonical in originals:
                raise ProductCanonizationValidationError(
                    "ean_canonico nao pode estar em eans_originais."
                )

            if await self.db.get(Department, department_id) is None:
                raise ProductCanonizationNotFoundError("Departamento nao encontrado.")

            await self._ensure_products_exist([canonical, *originals])
            await self._ensure_no_existing_mapping(department_id, originals)
            await self._ensure_no_ambiguous_chain(department_id, canonical, originals)

            confirmed_at = datetime.now(timezone.utc)
            created: list[CanonizationCreatedMapping] = []
            for original in originals:
                mapping = CanonizacaoProduto(
                    department_id=department_id,
                    ean_original=original,
                    ean_canonico=canonical,
                    status=ACTIVE_STATUS,
                    reason=safe_reason,
                    confirmado_por=safe_usuario,
                    confirmado_em=confirmed_at,
                )
                self.db.add(mapping)
                self.db.add(
                    AuditLog(
                        department_id=department_id,
                        usuario=safe_usuario,
                        operacao=PRODUCT_CANONIZED_OPERATION,
                        entidade="CanonizacaoProduto",
                        entidade_id=f"{department_id}:{original}",
                        detalhes=json.dumps(
                            {
                                "department_id": str(department_id),
                                "ean_original": original,
                                "ean_canonico": canonical,
                                "usuario_executor": safe_usuario,
                                "reason": safe_reason,
                                "origem": "manual",
                            },
                            ensure_ascii=True,
                            sort_keys=True,
                        ),
                    )
                )
                created.append(
                    CanonizationCreatedMapping(
                        ean_original=original,
                        ean_canonico=canonical,
                        status=ACTIVE_STATUS,
                    )
                )

            await self.db.flush()
            await self.db.commit()
            return CanonizationConfirmationResult(
                ean_canonico=canonical,
                department_id=department_id,
                created_mappings=created,
            )
        except Exception:
            await self.db.rollback()
            raise

    async def _ensure_products_exist(self, eans: list[str]) -> None:
        expected = set(eans)
        result = await self.db.execute(select(Produto.ean).where(Produto.ean.in_(expected)))
        existing = set(result.scalars().all())
        missing = sorted(expected - existing)
        if missing:
            raise ProductCanonizationNotFoundError(
                f"Produto(s) nao encontrado(s): {', '.join(missing)}."
            )

    async def _ensure_no_existing_mapping(
        self,
        department_id: UUID,
        originals: list[str],
    ) -> None:
        result = await self.db.execute(
            select(CanonizacaoProduto.ean_original, CanonizacaoProduto.status).where(
                CanonizacaoProduto.department_id == department_id,
                CanonizacaoProduto.ean_original.in_(originals),
            )
        )
        existing = result.all()
        if existing:
            active = sorted(row.ean_original for row in existing if row.status == ACTIVE_STATUS)
            blocked = active or sorted(row.ean_original for row in existing)
            raise ProductCanonizationConflictError(
                f"Mapeamento ja existente para ean_original: {', '.join(blocked)}."
            )

    async def _ensure_no_ambiguous_chain(
        self,
        department_id: UUID,
        canonical: str,
        originals: list[str],
    ) -> None:
        canonical_as_original = await self.db.scalar(
            select(CanonizacaoProduto.ean_canonico).where(
                CanonizacaoProduto.department_id == department_id,
                CanonizacaoProduto.ean_original == canonical,
                CanonizacaoProduto.status == ACTIVE_STATUS,
            )
        )
        if canonical_as_original is not None:
            raise ProductCanonizationConflictError(
                "ean_canonico ja esta ativo como ean_original neste departamento."
            )

        result = await self.db.execute(
            select(CanonizacaoProduto.ean_original).where(
                CanonizacaoProduto.department_id == department_id,
                CanonizacaoProduto.ean_canonico.in_(originals),
                CanonizacaoProduto.status == ACTIVE_STATUS,
            )
        )
        chained_originals = sorted(set(result.scalars().all()))
        if chained_originals:
            raise ProductCanonizationConflictError(
                "ean_original ja e ean_canonico ativo de outro mapeamento neste departamento."
            )


def _sanitize_ean(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ProductCanonizationValidationError(f"{field_name} e obrigatorio.")
    if len(normalized) > 32:
        raise ProductCanonizationValidationError(f"{field_name} deve ter no maximo 32 caracteres.")
    return normalized


def _sanitize_original_eans(values: list[str]) -> list[str]:
    if not isinstance(values, list):
        raise ProductCanonizationValidationError("eans_originais deve ser uma lista.")
    if not 1 <= len(values) <= MAX_ORIGINAL_EANS:
        raise ProductCanonizationValidationError(
            f"eans_originais deve ter entre 1 e {MAX_ORIGINAL_EANS} itens."
        )

    originals = [_sanitize_ean(value, "ean_original") for value in values]
    if len(set(originals)) != len(originals):
        raise ProductCanonizationValidationError("eans_originais nao pode conter duplicados.")
    return originals


def _sanitize_reason(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    return normalized[:MAX_REASON_LENGTH]


def _sanitize_usuario(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ProductCanonizationValidationError("usuario_executor e obrigatorio.")
    return normalized[:100]
