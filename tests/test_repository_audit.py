import pytest
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from backend.models.compras import AuditLog, Produto
from backend.services.repository import ProcurementRepository
from backend.schemas.internal import NotaFiscalDTO, FornecedorDTO, ItemNotaDTO
from backend.core.database import SessionLocal


@pytest.mark.asyncio
async def test_bulk_persistence_and_audit():
    """
    Valida a otimização de bulk insert do repositório e a geração de log de auditoria.
    """
    async with SessionLocal() as db:
        repo = ProcurementRepository(db)

        chave_unica = f"TEST{uuid4().hex}5225061234567800019955001"[:44]

        # 1. Prepara DTO com vários itens (alguns repetidos para testar cache)
        dto = NotaFiscalDTO(
            chave_acesso=chave_unica,
            numero_nota="999",
            data_emissao=date.today(),
            valor_total=Decimal("300.00"),
            fornecedor=FornecedorDTO(
                cnpj="99999999000199",
                razao_social="MERCADO AUDITORIA LTDA"
            ),
            itens=[
                ItemNotaDTO(ean="ITEM_A", descricao="PRODUTO A", quantidade=1, valor_unitario=100, valor_total=100),
                ItemNotaDTO(ean="ITEM_B", descricao="PRODUTO B", quantidade=2, valor_unitario=50, valor_total=100),
                ItemNotaDTO(ean="ITEM_A", descricao="PRODUTO A (CACHE)", quantidade=1, valor_unitario=100, valor_total=100),
            ]
        )

        # 2. Executa salvamento e auditoria na mesma transação
        async with db.begin():
            nota = await repo.salvar_nota_completa(dto.chave_acesso, dto)
            await repo.registrar_auditoria(
                usuario="admin",
                operacao="TEST_BULK",
                entidade="NotaFiscal",
                entidade_id=dto.chave_acesso,
                detalhes="Teste de auditoria e bulk insert",
                ip="127.0.0.1"
            )

        assert nota.chave_acesso == dto.chave_acesso

        # 3. Verificações no Banco
        # Deve ter criado apenas 2 produtos únicos apesar de 3 itens
        res_prod = await db.execute(select(Produto).where(Produto.ean.in_(["ITEM_A", "ITEM_B"])))
        produtos = res_prod.scalars().all()
        assert len(produtos) == 2

        # Verifica se o log de auditoria foi persistido
        res_audit = await db.execute(select(AuditLog).where(AuditLog.entidade_id == dto.chave_acesso))
        log = res_audit.scalar_one()
        assert log.usuario == "admin"
        assert log.operacao == "TEST_BULK"
        assert json.loads(log.detalhes) == {"message": "Teste de auditoria e bulk insert"}


@pytest.mark.asyncio
async def test_registrar_auditoria_redige_detalhes_sensiveis():
    async with SessionLocal() as db:
        repo = ProcurementRepository(db)
        audit_entity_id = f"audit-{uuid4()}"

        async with db.begin():
            await repo.registrar_auditoria(
                usuario="admin",
                operacao="TEST_REDACTION",
                entidade="NotaFiscal",
                entidade_id=audit_entity_id,
                detalhes={
                    "action": "UPDATE",
                    "reason": "Ajuste operacional",
                    "payload" + "_bruto": {"chave" + "_acesso": "1" * 44},
                    "descricao" + "_original": "ITEM FISCAL CRU",
                    "categoria": "MERCEARIA",
                },
                ip="127.0.0.1",
            )

        log = await db.scalar(select(AuditLog).where(AuditLog.entidade_id == audit_entity_id))
        detalhes = json.loads(log.detalhes)

    assert detalhes == {
        "action": "UPDATE",
        "categoria": "MERCEARIA",
        "reason": "Ajuste operacional",
    }
    rendered = json.dumps(detalhes, ensure_ascii=False).lower()
    assert "payload" + "_bruto" not in rendered
    assert "descricao" + "_original" not in rendered
    assert "chave" + "_acesso" not in rendered
