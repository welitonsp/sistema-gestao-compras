from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, func, select
from unittest.mock import AsyncMock

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import (
    AuditLog,
    ClassificacaoCache,
    Fornecedor,
    HistoricoPreco,
    ItemNotaFiscal,
    NotaFiscal,
    Produto,
    User,
    UserRole,
)
from backend.schemas.importacao import (
    FornecedorImportadoResponse,
    ImportacaoNotaResponse,
    ItemNotaFiscalImportadoResponse,
    NotaFiscalImportadaResponse,
)
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.importador_sefaz import ImportadorSefazService, SefazComunicacaoError
from backend.services.parsers.sefaz_go import SefazGoParser


def _valid_access_key(seed: str) -> str:
    base = seed[:43].ljust(43, "0")
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(digit) * weights[i % len(weights)] for i, digit in enumerate(base[::-1]))
    remainder = total % 11
    check_digit = 0 if remainder in (0, 1) else 11 - remainder
    return f"{base}{check_digit}"


async def _create_user(username: str, role: str = UserRole.ADMIN) -> str:
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.username == username))
        db.add(
            User(
                username=username,
                email=f"{username}@test.local",
                hashed_password="unused",
                role=role,
                is_active=True,
            )
        )
        await db.commit()
    return create_access_token({"sub": username, "role": role})


async def _count(model) -> int:
    async with SessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(model)) or 0


def _mock_import_dependencies(monkeypatch, dto: NotaFiscalDTO) -> None:
    async def fake_fetch_url(self, url: str) -> str:
        return "<html>nota fiscal mockada</html>"

    async def fake_classificar_itens_lote(self, itens, categorias_contexto):
        for item in itens:
            if item.categoria:
                item.categoria_sugerida_origem = "groq"
                item.categoria_sugerida_modelo = "test-model"
        return itens

    monkeypatch.setattr(ImportadorSefazService, "_fetch_url", fake_fetch_url)
    monkeypatch.setattr(SefazGoParser, "parse", lambda self, html: dto)
    monkeypatch.setattr(AIStructuredExtractor, "classificar_itens_lote", fake_classificar_itens_lote)
    app.state.http_client = AsyncMock()


def _mock_ai_fallback_import_dependencies(monkeypatch, dto: NotaFiscalDTO) -> None:
    async def fake_fetch_url(self, url: str) -> str:
        return "<html>sem seletores deterministas</html>"

    async def fake_extrair_nota(self, texto_limpo: str, categorias_contexto=None):
        return dto

    monkeypatch.setattr(ImportadorSefazService, "_fetch_url", fake_fetch_url)
    monkeypatch.setattr(SefazGoParser, "parse", lambda self, html: None)
    monkeypatch.setattr(AIStructuredExtractor, "extrair_nota", fake_extrair_nota)
    app.state.http_client = AsyncMock()


@pytest.mark.anyio
async def test_importacao_por_chave_persiste_nota_fornecedor_e_itens(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511810")
    token = await _create_user("import_admin")

    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40935",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("18.90"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001183",
            razao_social="MERCADO TESTE IMPORTACAO LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean="7891000000001",
                descricao="ARROZ TESTE 5KG",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("18.90"),
                valor_total=Decimal("18.90"),
                marca="TESTE",
                categoria="ALIMENTOS BASICOS",
            )
        ],
    )

    _mock_import_dependencies(monkeypatch, dto)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    response_nota = response.json()["nota_fiscal"]
    assert response_nota["chave_acesso"] == chave
    assert response_nota["extraction_quality_status"] == "ok"
    assert response_nota["extraction_parser_source"] == "deterministic"
    assert response_nota["extraction_item_count"] == 1
    assert response_nota["extraction_missing_ean_count"] == 0
    assert response_nota["extraction_total_mismatch"] is False
    assert response_nota["extraction_quality_details"] is not None

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        fornecedor = await db.scalar(select(Fornecedor).where(Fornecedor.cnpj == "17457404001183"))
        itens = (
            await db.execute(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))
        ).scalars().all()
        produto = await db.scalar(select(Produto).where(Produto.ean == "7891000000001"))
        historico = await db.scalar(select(HistoricoPreco).where(HistoricoPreco.ean == "7891000000001"))
        auditoria = await db.scalar(select(AuditLog).where(AuditLog.entidade_id == chave))

    assert nota is not None
    assert fornecedor is not None
    assert len(itens) == 1
    assert itens[0].categoria_sugerida == "ALIMENTOS BASICOS"
    assert itens[0].categoria_sugerida_origem == "groq"
    assert itens[0].categoria_sugerida_modelo == "test-model"
    assert produto is not None
    assert produto.categoria == "ALIMENTOS BASICOS"
    assert historico is not None
    assert nota.status == "active"
    assert nota.archived_at is None
    assert nota.archived_by is None
    assert nota.archive_reason is None
    assert nota.extraction_quality_status == "ok"
    assert nota.extraction_parser_source == "deterministic"
    assert nota.extraction_item_count == 1
    assert nota.extraction_missing_ean_count == 0
    assert nota.extraction_empty_description_count == 0
    assert nota.extraction_invalid_quantity_count == 0
    assert nota.extraction_invalid_value_count == 0
    assert nota.extraction_total_itens == Decimal("18.90")
    assert nota.extraction_total_nota == Decimal("18.90")
    assert nota.extraction_total_mismatch is False
    detalhes_qualidade = json.loads(nota.extraction_quality_details)
    assert detalhes_qualidade["quality_status"] == "ok"
    assert detalhes_qualidade["parser_source"] == "deterministic"
    assert historico.nota_fiscal_id == nota.id
    assert historico.item_nota_fiscal_id == itens[0].id
    assert auditoria is not None


@pytest.mark.anyio
async def test_importacao_por_chave_sem_ean_grava_warning_qualidade(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127519870")
    token = await _create_user("import_missing_ean_admin")
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40940",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("5.00"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001988",
            razao_social="MERCADO QUALIDADE SEM EAN LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean="SEM_EAN_QUALIDADE01",
                descricao="PRODUTO SEM EAN TESTE",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("5.00"),
                valor_total=Decimal("5.00"),
                categoria="OUTROS",
            )
        ],
    )
    _mock_import_dependencies(monkeypatch, dto)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    response_nota = response.json()["nota_fiscal"]
    assert response_nota["extraction_quality_status"] == "warning"
    assert response_nota["extraction_parser_source"] == "deterministic"
    assert response_nota["extraction_missing_ean_count"] == 1

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))

    assert nota.extraction_quality_status == "warning"
    assert nota.extraction_parser_source == "deterministic"
    assert nota.extraction_missing_ean_count == 1
    assert nota.extraction_total_mismatch is False


@pytest.mark.anyio
async def test_importacao_por_chave_divergencia_total_grava_warning_qualidade(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127519880")
    token = await _create_user("import_total_mismatch_admin")
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40941",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("40.00"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001989",
            razao_social="MERCADO QUALIDADE DESCONTO LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean="7891000000201",
                descricao="CAFE QUALIDADE 500G",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("25.00"),
                valor_total=Decimal("25.00"),
                categoria="ALIMENTOS BASICOS",
            ),
            ItemNotaDTO(
                ean="7891000000202",
                descricao="ACUCAR QUALIDADE 5KG",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("20.00"),
                valor_total=Decimal("20.00"),
                categoria="ALIMENTOS BASICOS",
            ),
        ],
    )
    _mock_import_dependencies(monkeypatch, dto)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    response_nota = response.json()["nota_fiscal"]
    assert response_nota["extraction_quality_status"] == "warning"
    assert response_nota["extraction_parser_source"] == "deterministic"
    assert response_nota["extraction_total_mismatch"] is True

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))

    assert nota.extraction_quality_status == "warning"
    assert nota.extraction_parser_source == "deterministic"
    assert nota.extraction_total_itens == Decimal("45.00")
    assert nota.extraction_total_nota == Decimal("40.00")
    assert nota.extraction_total_mismatch is True


@pytest.mark.anyio
async def test_importacao_por_chave_fallback_ia_mockado_grava_parser_source(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127519890")
    token = await _create_user("import_ai_fallback_admin")
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40942",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("9.90"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001990",
            razao_social="MERCADO QUALIDADE FALLBACK LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean="7891000000203",
                descricao="ITEM FALLBACK QUALIDADE",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("9.90"),
                valor_total=Decimal("9.90"),
                categoria="OUTROS",
                categoria_sugerida_origem="groq",
                categoria_sugerida_modelo="mock-groq",
            )
        ],
    )
    _mock_ai_fallback_import_dependencies(monkeypatch, dto)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    response_nota = response.json()["nota_fiscal"]
    assert response_nota["extraction_quality_status"] == "ok"
    assert response_nota["extraction_parser_source"] == "ai_fallback"

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))
        item = await db.scalar(select(ItemNotaFiscal).where(ItemNotaFiscal.nota_fiscal_id == nota.id))

    assert nota.extraction_quality_status == "ok"
    assert nota.extraction_parser_source == "ai_fallback"
    assert item.categoria_sugerida == "OUTROS"
    assert item.categoria_sugerida_origem == "groq"


@pytest.mark.anyio
async def test_nota_antiga_sem_score_qualidade_permanece_compativel():
    chave = _valid_access_key("5226051745740400118365511000040935127519900")

    async with SessionLocal() as db:
        fornecedor = Fornecedor(
            cnpj="17457404001991",
            razao_social="MERCADO LEGADO SEM QUALIDADE LTDA",
        )
        db.add(fornecedor)
        await db.flush()
        db.add(
            NotaFiscal(
                fornecedor_id=fornecedor.id,
                numero_nota="40943",
                chave_acesso=chave,
                data_emissao=date(2026, 5, 26),
                valor_total=Decimal("1.00"),
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        nota = await db.scalar(select(NotaFiscal).where(NotaFiscal.chave_acesso == chave))

    assert nota.extraction_quality_status is None
    assert nota.extraction_parser_source is None
    assert nota.extraction_quality_details is None


@pytest.mark.anyio
async def test_importacao_por_chave_nao_sobrescreve_categoria_confirmada(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127519850")
    token = await _create_user("import_confirmed_admin")
    ean = "7891000000199"

    async with SessionLocal() as db:
        db.add(
            Produto(
                ean=ean,
                nome_limpo="PRODUTO JA CONFIRMADO",
                marca="HUMANA",
                categoria="CATEGORIA HUMANA",
                categoria_confirmada="CATEGORIA HUMANA",
                categoria_confirmada_por="gestor",
                categoria_confirmada_em=datetime.now(timezone.utc),
                categoria_confirmada_origem="manual",
                unidade="un",
            )
        )
        await db.commit()

    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40938",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("12.00"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001986",
            razao_social="MERCADO CONFIRMACAO TESTE LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean=ean,
                descricao="PRODUTO COM SUGESTAO IA",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("12.00"),
                valor_total=Decimal("12.00"),
                marca="IA",
                categoria="CATEGORIA IA",
            )
        ],
    )
    _mock_import_dependencies(monkeypatch, dto)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201

    async with SessionLocal() as db:
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        item = await db.scalar(
            select(ItemNotaFiscal)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
            .where(NotaFiscal.chave_acesso == chave)
        )

    assert produto.categoria == "CATEGORIA HUMANA"
    assert produto.categoria_confirmada == "CATEGORIA HUMANA"
    assert produto.categoria_confirmada_por == "gestor"
    assert produto.categoria_confirmada_origem == "manual"
    assert item.categoria_sugerida == "CATEGORIA IA"
    assert item.categoria_sugerida_origem == "groq"


@pytest.mark.anyio
async def test_patch_produto_categoria_preenche_confirmacao_manual():
    chave = _valid_access_key("5226051745740400118365511000040935127511860")
    token = await _create_user("catalog_confirm_manager", UserRole.MANAGER)
    ean = "7891000000100"

    async with SessionLocal() as db:
        fornecedor = Fornecedor(
            cnpj="17457404001187",
            razao_social="MERCADO PATCH CATEGORIA LTDA",
        )
        produto = Produto(
            ean=ean,
            nome_limpo="PRODUTO PATCH CATEGORIA",
            marca="ANTIGA",
            categoria="ANTIGA",
            unidade="un",
        )
        db.add_all([fornecedor, produto])
        await db.flush()

        nota = NotaFiscal(
            fornecedor_id=fornecedor.id,
            numero_nota="40939",
            chave_acesso=chave,
            data_emissao=date(2026, 5, 26),
            valor_total=Decimal("7.50"),
        )
        db.add(nota)
        await db.flush()

        db.add(
            ItemNotaFiscal(
                nota_fiscal_id=nota.id,
                ean=ean,
                descricao_original="PRODUTO PATCH DESCRICAO ORIGINAL",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("7.50"),
                valor_total=Decimal("7.50"),
                categoria_sugerida="CATEGORIA SUGERIDA IA",
                categoria_sugerida_origem="groq",
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/produtos/{ean}",
            json={"categoria": "CATEGORIA CONFIRMADA", "marca": "NOVA"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200

    async with SessionLocal() as db:
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        cache = await db.scalar(
            select(ClassificacaoCache).where(
                ClassificacaoCache.descricao_original == "PRODUTO PATCH DESCRICAO ORIGINAL"
            )
        )
        audit_log = await db.scalar(
            select(AuditLog).where(
                AuditLog.operacao == "CATEGORY_CONFIRMED",
                AuditLog.entidade == "Produto",
                AuditLog.entidade_id == ean,
            )
        )

    assert produto.categoria == "CATEGORIA CONFIRMADA"
    assert produto.categoria_confirmada == "CATEGORIA CONFIRMADA"
    assert produto.categoria_confirmada_por == "catalog_confirm_manager"
    assert produto.categoria_confirmada_em is not None
    assert produto.categoria_confirmada_origem == "manual"
    assert cache is not None
    assert cache.categoria == "CATEGORIA CONFIRMADA"
    assert cache.marca == "NOVA"
    assert cache.verificado_usuario is True
    assert audit_log is not None
    detalhes = json.loads(audit_log.detalhes)
    assert audit_log.usuario == "catalog_confirm_manager"
    assert detalhes["categoria_anterior"] == "ANTIGA"
    assert detalhes["categoria_nova"] == "CATEGORIA CONFIRMADA"
    assert detalhes["origem"] == "manual"
    assert detalhes["usuario"] == "catalog_confirm_manager"
    assert detalhes["produto"] == "PRODUTO PATCH CATEGORIA"
    assert detalhes["categorias_sugeridas_relacionadas"] == ["CATEGORIA SUGERIDA IA"]


@pytest.mark.anyio
async def test_patch_produto_categoria_igual_nao_cria_auditlog():
    token = await _create_user("catalog_same_category_manager", UserRole.MANAGER)
    ean = "7891000000101"

    async with SessionLocal() as db:
        db.add(
            Produto(
                ean=ean,
                nome_limpo="PRODUTO MESMA CATEGORIA",
                marca="ANTIGA",
                categoria="CATEGORIA ATUAL",
                unidade="un",
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/produtos/{ean}",
            json={"categoria": "CATEGORIA ATUAL", "marca": "NOVA"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200

    async with SessionLocal() as db:
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        audit_count = await db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.operacao == "CATEGORY_CONFIRMED",
                AuditLog.entidade_id == ean,
            )
        )

    assert produto.categoria_confirmada == "CATEGORIA ATUAL"
    assert produto.categoria_confirmada_por == "catalog_same_category_manager"
    assert produto.categoria_confirmada_origem == "manual"
    assert audit_count == 0


@pytest.mark.anyio
async def test_patch_produto_sem_categoria_nao_cria_auditlog():
    token = await _create_user("catalog_brand_only_manager", UserRole.MANAGER)
    ean = "7891000000102"

    async with SessionLocal() as db:
        db.add(
            Produto(
                ean=ean,
                nome_limpo="PRODUTO SOMENTE MARCA",
                marca="ANTIGA",
                categoria="CATEGORIA ATUAL",
                unidade="un",
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/produtos/{ean}",
            json={"marca": "NOVA"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200

    async with SessionLocal() as db:
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        audit_count = await db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.operacao == "CATEGORY_CONFIRMED",
                AuditLog.entidade_id == ean,
            )
        )

    assert produto.marca == "NOVA"
    assert produto.categoria == "CATEGORIA ATUAL"
    assert produto.categoria_confirmada is None
    assert audit_count == 0


@pytest.mark.anyio
async def test_patch_produto_categoria_usuario_sem_permissao_nao_cria_auditlog():
    token = await _create_user("catalog_operator", UserRole.OPERATOR)
    ean = "7891000000103"

    async with SessionLocal() as db:
        db.add(
            Produto(
                ean=ean,
                nome_limpo="PRODUTO BLOQUEADO",
                marca="ANTIGA",
                categoria="CATEGORIA ATUAL",
                unidade="un",
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/produtos/{ean}",
            json={"categoria": "CATEGORIA BLOQUEADA"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403

    async with SessionLocal() as db:
        produto = await db.scalar(select(Produto).where(Produto.ean == ean))
        audit_count = await db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.operacao == "CATEGORY_CONFIRMED",
                AuditLog.entidade_id == ean,
            )
        )

    assert produto.categoria == "CATEGORIA ATUAL"
    assert produto.categoria_confirmada is None
    assert audit_count == 0


@pytest.mark.anyio
async def test_importacao_por_chave_reimportacao_retorna_409_sem_duplicar(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511830")
    token = await _create_user("import_duplicate_admin")
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota="40936",
        data_emissao=date(2026, 5, 26),
        valor_total=Decimal("22.50"),
        fornecedor=FornecedorDTO(
            cnpj="17457404001184",
            razao_social="MERCADO DUPLICIDADE TESTE LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean="7891000000002",
                descricao="FEIJAO TESTE 1KG",
                quantidade=Decimal("1"),
                valor_unitario=Decimal("22.50"),
                valor_total=Decimal("22.50"),
                marca="TESTE",
                categoria="ALIMENTOS BASICOS",
            )
        ],
    )
    _mock_import_dependencies(monkeypatch, dto)

    before = {
        NotaFiscal: await _count(NotaFiscal),
        Fornecedor: await _count(Fornecedor),
        ItemNotaFiscal: await _count(ItemNotaFiscal),
        Produto: await _count(Produto),
        HistoricoPreco: await _count(HistoricoPreco),
        AuditLog: await _count(AuditLog),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )
        second_response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert "ja cadastrada" in second_response.json()["detail"]
    assert chave not in second_response.text
    assert await _count(NotaFiscal) == before[NotaFiscal] + 1
    assert await _count(Fornecedor) == before[Fornecedor] + 1
    assert await _count(ItemNotaFiscal) == before[ItemNotaFiscal] + 1
    assert await _count(Produto) == before[Produto] + 1
    assert await _count(HistoricoPreco) == before[HistoricoPreco] + 1
    assert await _count(AuditLog) == before[AuditLog] + 1


@pytest.mark.anyio
async def test_importacao_por_chave_integrity_error_retorna_409_sem_traceback(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511840")
    token = await _create_user("import_integrity_admin")
    rollback_called = False

    async def fake_importar_por_chave(self, **kwargs):
        return ImportacaoNotaResponse(
            mensagem="Nota fiscal importada com sucesso.",
            fornecedor=FornecedorImportadoResponse(
                id="00000000-0000-0000-0000-000000000001",
                cnpj="17457404001185",
                razao_social="MERCADO INTEGRITY TESTE LTDA",
            ),
            nota_fiscal=NotaFiscalImportadaResponse(
                id="00000000-0000-0000-0000-000000000002",
                numero_nota="40937",
                chave_acesso=chave,
                data_emissao=date(2026, 5, 26),
                valor_total=Decimal("10.00"),
            ),
            itens=[
                ItemNotaFiscalImportadoResponse(
                    id="00000000-0000-0000-0000-000000000003",
                    ean="7891000000003",
                    descricao_original="CAFE TESTE 500G",
                    quantidade=Decimal("1"),
                    valor_unitario=Decimal("10.00"),
                    valor_total=Decimal("10.00"),
                )
            ],
            total_itens=1,
        )

    async def fail_commit(self):
        raise IntegrityError(
            "INSERT INTO notas_fiscais",
            {},
            Exception("UNIQUE constraint failed: notas_fiscais.chave_acesso"),
        )

    async def track_rollback(self):
        nonlocal rollback_called
        rollback_called = True

    monkeypatch.setattr(ImportadorSefazService, "importar_por_chave", fake_importar_por_chave)
    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.commit", fail_commit)
    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.rollback", track_rollback)
    app.state.http_client = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 409
    assert "ja cadastrada" in response.json()["detail"]
    assert "IntegrityError" not in response.text
    assert chave not in response.text
    assert rollback_called is True


@pytest.mark.anyio
async def test_importacao_por_chave_falha_externa_nao_persiste(monkeypatch):
    chave = _valid_access_key("5226051745740400118365511000040935127511820")
    token = await _create_user("import_failure_admin")
    before = {
        NotaFiscal: await _count(NotaFiscal),
        Fornecedor: await _count(Fornecedor),
        ItemNotaFiscal: await _count(ItemNotaFiscal),
        Produto: await _count(Produto),
        HistoricoPreco: await _count(HistoricoPreco),
        AuditLog: await _count(AuditLog),
    }

    async def fail_fetch_url(self, url: str) -> str:
        raise SefazComunicacaoError("SEFAZ indisponivel no teste")

    monkeypatch.setattr(ImportadorSefazService, "_fetch_url", fail_fetch_url)
    app.state.http_client = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notas/importacao-por-chave",
            json={"chave_acesso": chave},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
    assert await _count(NotaFiscal) == before[NotaFiscal]
    assert await _count(Fornecedor) == before[Fornecedor]
    assert await _count(ItemNotaFiscal) == before[ItemNotaFiscal]
    assert await _count(Produto) == before[Produto]
    assert await _count(HistoricoPreco) == before[HistoricoPreco]
    assert await _count(AuditLog) == before[AuditLog]
