"""End-to-end integration test for the new Procurement Architecture."""

import asyncio
import sys
import time
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from backend.core.database import SessionLocal, engine
from backend.models.base import Base
from backend.models.compras import Fornecedor, NotaFiscal, Produto
from backend.services.importador_sefaz import ImportadorSefazService
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO


async def setup_db():
    print("🛠️  Resetando tabelas de teste...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tabelas prontas.")


import pytest

@pytest.mark.asyncio
async def test_manual_persistence():
    print("\n📝 Testando persistência manual via Repository (interno)...")
    async with SessionLocal() as db:
        service = ImportadorSefazService(db)
        
        # Simula um DTO que viria da IA
        dto = NotaFiscalDTO(
            chave_acesso="52250612345678000199550010000123451000123456",
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
                ),
                ItemNotaDTO(
                    ean="7890000111222",
                    descricao="FEIJAO CARIOCA 1KG",
                    quantidade=Decimal("2"),
                    valor_unitario=Decimal("10.25"),
                    valor_total=Decimal("20.50")
                )
            ]
        )
        
        chave = f"TEST{int(time.time())}5225061234567800019955001"[:44]
        # Garante que o DTO use a mesma chave
        dto.chave_acesso = chave
        nota = await service.repo.salvar_nota_completa(chave, dto)
        await db.commit()
        
        print(f"✅ Nota salva: ID {nota.id}")
        
        # Verificações
        stmt_prod = select(Produto).where(Produto.ean == "7891234567890")
        prod = await db.scalar(stmt_prod)
        print(f"📦 Produto no catálogo: {prod.nome_limpo} | Categoria: {prod.categoria}")
        
        assert prod.ean == "7891234567890"
        print("🚀 Persistência manual validada com sucesso!")


async def main():
    try:
        await setup_db()
        await test_manual_persistence()
        print("\n✨ TODOS OS TESTES PASSARAM! A ARQUITETURA ESTÁ SÓLIDA. ✨")
    except Exception as e:
        print(f"\n❌ FALHA NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
