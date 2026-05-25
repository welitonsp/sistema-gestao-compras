"""End-to-end integration test for the new Procurement Architecture."""

import asyncio
import sys
import time
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from backend.core.database import SessionLocal, engine
from backend.models.base import Base
from backend.models.compras import Fornecedor, NotaFiscal, Produto, AuditLog
from backend.services.importador_sefaz import ImportadorSefazService
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO
from unittest.mock import AsyncMock
import httpx
import pytest

@pytest.mark.asyncio
async def test_manual_persistence():
    print("\n📝 Testando persistência manual via Repository (interno)...")
    async with SessionLocal() as db:
        # Mock do HttpClient exigido pelo novo construtor
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        service = ImportadorSefazService(db, http_client=mock_client)
        
        # Simula um DTO que viria da IA
        chave = f"TEST{int(time.time())}5225061234567800019955001"[:44]
        dto = NotaFiscalDTO(
            chave_acesso=chave,
            numero_nota="12345",
            data_emissao=date.today(),
            valor_total=Decimal("100.50"),
            fornecedor=FornecedorDTO(
                cnpj="12345678000199",
                razao_social="MERCADO TESTE LTDA"
            ),
            itens=[
                ItemNotaDTO(
                    ean="7891234567890",
                    descricao="ARROZ TIO JOAO 5KG",
                    quantidade=Decimal("1"),
                    valor_unitario=Decimal("30.00"),
                    valor_total=Decimal("30.00")
                )
            ]
        )
        
        # Executa salvamento
        nota = await service.repo.salvar_nota_completa(chave, dto)
        await db.commit()
        
        print(f"✅ Nota salva: ID {nota.id}")
        
        # Verificações
        stmt_prod = select(Produto).where(Produto.ean == "7891234567890")
        prod = await db.scalar(stmt_prod)
        assert prod is not None
        assert prod.ean == "7891234567890"
        print("🚀 Persistência manual validada!")
