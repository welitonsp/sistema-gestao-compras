from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.core.database import SessionLocal
from backend.models.compras import Department, Fornecedor, ItemNotaFiscal, NotaFiscal, Produto
from backend.services.repository import ProcurementRepository


@pytest.mark.asyncio
async def test_obter_categorias_unicas_respeita_department_id_e_status():
    dept_a = uuid4()
    dept_b = uuid4()
    categories = {
        "a": "H10D CATEGORIA TENANT A",
        "b": "H10D CATEGORIA TENANT B",
        "archived": "H10D CATEGORIA ARQUIVADA",
        "global": "H10D CATEGORIA GLOBAL SEM COMPRA",
    }

    async with SessionLocal() as db:
        db.add_all(
            [
                Department(id=dept_a, name=f"H10D Dept A {dept_a}", is_active=True),
                Department(id=dept_b, name=f"H10D Dept B {dept_b}", is_active=True),
                Produto(
                    ean=f"H10D-A-{dept_a.hex[:8]}",
                    nome_limpo="H10D Produto A",
                    categoria=categories["a"],
                    unidade="un",
                ),
                Produto(
                    ean=f"H10D-B-{dept_b.hex[:8]}",
                    nome_limpo="H10D Produto B",
                    categoria=categories["b"],
                    unidade="un",
                ),
                Produto(
                    ean=f"H10D-X-{dept_a.hex[:8]}",
                    nome_limpo="H10D Produto Arquivado",
                    categoria=categories["archived"],
                    unidade="un",
                ),
                Produto(
                    ean=f"H10D-G-{dept_a.hex[:8]}",
                    nome_limpo="H10D Produto Global",
                    categoria=categories["global"],
                    unidade="un",
                ),
            ]
        )
        fornecedor = Fornecedor(
            cnpj=f"99{dept_a.hex[:12]}",
            razao_social="H10D FORNECEDOR TESTE",
        )
        db.add(fornecedor)
        await db.flush()

        nota_a = NotaFiscal(
            fornecedor_id=fornecedor.id,
            department_id=dept_a,
            numero_nota=f"H10D-A-{dept_a.hex[:6]}",
            chave_acesso=f"H10D-A-{dept_a.hex}",
            data_emissao=date(2026, 6, 9),
            valor_total=Decimal("10.00"),
            status="active",
        )
        nota_b = NotaFiscal(
            fornecedor_id=fornecedor.id,
            department_id=dept_b,
            numero_nota=f"H10D-B-{dept_b.hex[:6]}",
            chave_acesso=f"H10D-B-{dept_b.hex}",
            data_emissao=date(2026, 6, 9),
            valor_total=Decimal("10.00"),
            status="active",
        )
        nota_archived = NotaFiscal(
            fornecedor_id=fornecedor.id,
            department_id=dept_a,
            numero_nota=f"H10D-X-{dept_a.hex[:6]}",
            chave_acesso=f"H10D-X-{dept_a.hex}",
            data_emissao=date(2026, 6, 9),
            valor_total=Decimal("10.00"),
            status="archived",
        )
        db.add_all([nota_a, nota_b, nota_archived])
        await db.flush()

        db.add_all(
            [
                ItemNotaFiscal(
                    nota_fiscal_id=nota_a.id,
                    ean=f"H10D-A-{dept_a.hex[:8]}",
                    descricao_original="H10D ITEM A",
                    quantidade=Decimal("1"),
                    valor_unitario=Decimal("10.00"),
                    valor_total=Decimal("10.00"),
                ),
                ItemNotaFiscal(
                    nota_fiscal_id=nota_b.id,
                    ean=f"H10D-B-{dept_b.hex[:8]}",
                    descricao_original="H10D ITEM B",
                    quantidade=Decimal("1"),
                    valor_unitario=Decimal("10.00"),
                    valor_total=Decimal("10.00"),
                ),
                ItemNotaFiscal(
                    nota_fiscal_id=nota_archived.id,
                    ean=f"H10D-X-{dept_a.hex[:8]}",
                    descricao_original="H10D ITEM ARQUIVADO",
                    quantidade=Decimal("1"),
                    valor_unitario=Decimal("10.00"),
                    valor_total=Decimal("10.00"),
                ),
            ]
        )
        await db.commit()

    async with SessionLocal() as db:
        repo = ProcurementRepository(db)
        scoped = await repo.obter_categorias_unicas(department_id=dept_a)
        global_categories = await repo.obter_categorias_unicas()

    assert categories["a"] in scoped
    assert categories["b"] not in scoped
    assert categories["archived"] not in scoped
    assert categories["global"] not in scoped
    assert categories["global"] in global_categories
