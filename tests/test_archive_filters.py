from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from backend.core.database import SessionLocal
from backend.core.security import create_access_token
from backend.main import app
from backend.models.compras import HistoricoPreco, NotaFiscal, Produto, User, UserRole
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from backend.services.import_archive_service import archive_importacao_por_chave
from backend.services.insights_processor import PriceInsightsService
from backend.services.repository import ProcurementRepository


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


async def _create_imported_note(
    *,
    chave: str,
    suffix: str,
    ean: str,
    categoria: str,
    valor_unitario: Decimal,
    data_emissao: date,
) -> None:
    dto = NotaFiscalDTO(
        chave_acesso=chave,
        numero_nota=f"70{suffix}",
        data_emissao=data_emissao,
        valor_total=valor_unitario,
        fornecedor=FornecedorDTO(
            cnpj=f"1745740402{suffix.zfill(4)}",
            razao_social=f"MERCADO FILTRO ARCHIVE {suffix} LTDA",
        ),
        itens=[
            ItemNotaDTO(
                ean=ean,
                descricao=f"PRODUTO FILTRO ARCHIVE {suffix}",
                quantidade=Decimal("1"),
                valor_unitario=valor_unitario,
                valor_total=valor_unitario,
                marca="TESTE",
                categoria=categoria,
            )
        ],
    )

    async with SessionLocal() as db:
        async with db.begin():
            repo = ProcurementRepository(db)
            await repo.salvar_nota_completa(chave, dto)
            await repo.registrar_auditoria(
                usuario="importador_teste",
                operacao="IMPORT_TEST",
                entidade="NotaFiscal",
                entidade_id=chave,
                detalhes="Importacao criada para teste de filtros de archive",
            )


async def _archive_note(chave: str) -> None:
    async with SessionLocal() as db:
        async with db.begin():
            await archive_importacao_por_chave(
                chave_acesso=chave,
                usuario="archive_filter_admin",
                motivo="archive para teste de filtros",
                db=db,
            )


@pytest.mark.anyio
async def test_dashboard_resumo_exclui_nota_arquivada_e_mantem_audit_log_visivel():
    chave = _valid_access_key("5226051745740400118365511000040935127512010")
    categoria = "ARCHIVE_FILTER_RESUMO_201"
    token = await _create_user("archive_filter_admin_201", UserRole.ADMIN)
    await _create_imported_note(
        chave=chave,
        suffix="201",
        ean="7893000000201",
        categoria=categoria,
        valor_unitario=Decimal("31.50"),
        data_emissao=date(2026, 5, 26),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get("/api/v1/dashboard/resumo", headers={"Authorization": f"Bearer {token}"})
    assert before.status_code == 200
    before_payload = before.json()
    assert any(
        item["categoria"] == categoria and float(item["total"]) == 31.5
        for item in before_payload["por_categoria"]
    ), before_payload

    await _archive_note(chave)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        after = await client.get("/api/v1/dashboard/resumo", headers={"Authorization": f"Bearer {token}"})
        audit = await client.get("/api/v1/dashboard/audit-logs", headers={"Authorization": f"Bearer {token}"})

    assert after.status_code == 200
    assert all(item["categoria"] != categoria for item in after.json()["por_categoria"])
    assert audit.status_code == 200
    assert any(log["entidade_id"] == chave and log["operacao"] == "IMPORT_ARCHIVED" for log in audit.json())


@pytest.mark.anyio
async def test_alertas_de_preco_ignoram_historico_vinculado_a_nota_arquivada():
    ean = "7893000000202"
    categoria = "ARCHIVE_FILTER_ALERTA_202"
    chave_active = _valid_access_key("5226051745740400118365511000040935127512020")
    chave_archived = _valid_access_key("5226051745740400118365511000040935127512030")
    await _create_imported_note(
        chave=chave_active,
        suffix="202",
        ean=ean,
        categoria=categoria,
        valor_unitario=Decimal("10.00"),
        data_emissao=date(2026, 5, 1),
    )
    await _create_imported_note(
        chave=chave_archived,
        suffix="203",
        ean=ean,
        categoria=categoria,
        valor_unitario=Decimal("100.00"),
        data_emissao=date(2026, 5, 2),
    )

    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        before = await service.detectar_variacoes_anomalas(threshold_percent=10)
    assert any(alerta["ean"] == ean for alerta in before)

    await _archive_note(chave_archived)

    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        after = await service.detectar_variacoes_anomalas(threshold_percent=10)
    assert all(alerta["ean"] != ean for alerta in after)


@pytest.mark.anyio
async def test_catalogo_oculta_produto_exclusivamente_arquivado_e_mantem_produto_ativo():
    archived_chave = _valid_access_key("5226051745740400118365511000040935127512040")
    active_chave = _valid_access_key("5226051745740400118365511000040935127512050")
    archived_ean = "7893000000204"
    active_ean = "7893000000205"
    token = await _create_user("archive_filter_admin_204", UserRole.ADMIN)

    await _create_imported_note(
        chave=archived_chave,
        suffix="204",
        ean=archived_ean,
        categoria="ARCHIVE_FILTER_CATALOGO_204",
        valor_unitario=Decimal("11.00"),
        data_emissao=date(2026, 5, 3),
    )
    await _create_imported_note(
        chave=active_chave,
        suffix="205",
        ean=active_ean,
        categoria="ARCHIVE_FILTER_CATALOGO_205",
        valor_unitario=Decimal("12.00"),
        data_emissao=date(2026, 5, 3),
    )
    await _archive_note(archived_chave)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/produtos?limit=500", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    eans = {produto["ean"] for produto in response.json()}
    assert archived_ean not in eans
    assert active_ean in eans


@pytest.mark.anyio
async def test_historico_legado_sem_nota_fiscal_id_continua_em_metricas():
    ean = "LEGACY_ARCHIVE_FILTER_206"
    async with SessionLocal() as db:
        async with db.begin():
            db.add(
                Produto(
                    ean=ean,
                    nome_limpo="PRODUTO LEGADO SEM NOTA",
                    marca="TESTE",
                    categoria="ARCHIVE_FILTER_LEGACY_206",
                    unidade="un",
                )
            )
            db.add_all(
                [
                    HistoricoPreco(
                        ean=ean,
                        data_compra=date(2026, 5, 1),
                        local="LEGADO",
                        preco_pago=Decimal("10.00"),
                        quantidade=Decimal("1"),
                    ),
                    HistoricoPreco(
                        ean=ean,
                        data_compra=date(2026, 5, 2),
                        local="LEGADO",
                        preco_pago=Decimal("15.00"),
                        quantidade=Decimal("1"),
                    ),
                ]
            )

    async with SessionLocal() as db:
        service = PriceInsightsService(db)
        alertas = await service.detectar_variacoes_anomalas(threshold_percent=10)
        volatilidade = await service.obter_produtos_mais_volateis(limit=20)

    assert any(alerta["ean"] == ean for alerta in alertas)
    assert any(item["produto"] == "PRODUTO LEGADO SEM NOTA" for item in volatilidade)
