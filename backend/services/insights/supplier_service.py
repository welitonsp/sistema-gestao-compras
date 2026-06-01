"""Supplier and note logic for insights."""

from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.compras import NotaFiscal, Fornecedor, Produto, ItemNotaFiscal
from .base import ACTIVE_INVOICE_STATUS

class SupplierService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def obter_top_fornecedores_gasto(
        self,
        limit: int = 10,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(
                Fornecedor.id,
                Fornecedor.razao_social,
                func.sum(NotaFiscal.valor_total).label("total"),
                func.count(NotaFiscal.id).label("quantidade_notas"),
                (func.sum(NotaFiscal.valor_total) / func.count(NotaFiscal.id)).label("ticket_medio"),
            )
            .join(NotaFiscal, Fornecedor.id == NotaFiscal.fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id: stmt = stmt.where(NotaFiscal.department_id == department_id)
        if start_date: stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date: stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        stmt = stmt.group_by(Fornecedor.id, Fornecedor.razao_social).order_by(desc("total")).limit(limit)
        result = await self.db.execute(stmt)
        return [
            {
                "fornecedor_id": str(row.id),
                "fornecedor": row.razao_social,
                "total": float(row.total),
                "quantidade_notas": row.quantidade_notas,
                "ticket_medio": float(row.ticket_medio or 0),
            }
            for row in result.fetchall()
        ]

    async def obter_drilldown_fornecedor(
        self,
        fornecedor_id: UUID | str,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 20,
    ) -> Dict[str, Any] | None:
        if isinstance(fornecedor_id, str):
             fornecedor_id = UUID(fornecedor_id)

        # 1. Fornecedor Info
        stmt_forn = select(Fornecedor).where(Fornecedor.id == fornecedor_id)
        fornecedor = await self.db.scalar(stmt_forn)
        if not fornecedor: return None
        nome_exibicao = fornecedor.nome_fantasia or fornecedor.razao_social

        # 2. Resumo
        stmt_resumo = (
            select(
                func.sum(NotaFiscal.valor_total).label("total_gasto"),
                func.count(NotaFiscal.id).label("quantidade_notas"),
                func.min(NotaFiscal.data_emissao).label("primeira_compra"),
                func.max(NotaFiscal.data_emissao).label("ultima_compra"),
            )
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id: stmt_resumo = stmt_resumo.where(NotaFiscal.department_id == department_id)
        if start_date: stmt_resumo = stmt_resumo.where(NotaFiscal.data_emissao >= start_date)
        if end_date: stmt_resumo = stmt_resumo.where(NotaFiscal.data_emissao <= end_date)

        resumo_row = (await self.db.execute(stmt_resumo)).first()
        total_gasto = resumo_row.total_gasto or Decimal("0")
        qtd_notas = resumo_row.quantidade_notas or 0
        ticket_medio = total_gasto / qtd_notas if qtd_notas > 0 else Decimal("0")

        # 2b. Cálculo de Concentração (Exact logic match)
        stmt_total_periodo = select(func.sum(NotaFiscal.valor_total)).where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        if department_id: stmt_total_periodo = stmt_total_periodo.where(NotaFiscal.department_id == department_id)
        if start_date: stmt_total_periodo = stmt_total_periodo.where(NotaFiscal.data_emissao >= start_date)
        if end_date: stmt_total_periodo = stmt_total_periodo.where(NotaFiscal.data_emissao <= end_date)
        total_periodo = await self.db.scalar(stmt_total_periodo) or Decimal("0")

        concentracao = None
        if total_periodo > 0:
            percentual = float((total_gasto / total_periodo) * 100)
            if percentual >= 50: nivel, msg = "danger", f"Concentração alta: este fornecedor representa {percentual:.1f}% dos seus gastos no período selecionado."
            elif percentual >= 30: nivel, msg = "warning", f"Atenção: este fornecedor concentra {percentual:.1f}% dos seus gastos no período selecionado."
            else: nivel, msg = "info", f"Este fornecedor representa {percentual:.1f}% dos seus gastos no período selecionado."
            concentracao = {"percentual": round(percentual, 1), "nivel": nivel, "mensagem": msg}

        # 3. Notas (Restore the list)
        stmt_notas = select(NotaFiscal.data_emissao, NotaFiscal.numero_nota, NotaFiscal.valor_total).where(NotaFiscal.fornecedor_id == fornecedor_id, NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        if department_id: stmt_notas = stmt_notas.where(NotaFiscal.department_id == department_id)
        if start_date: stmt_notas = stmt_notas.where(NotaFiscal.data_emissao >= start_date)
        if end_date: stmt_notas = stmt_notas.where(NotaFiscal.data_emissao <= end_date)
        stmt_notas = stmt_notas.order_by(desc(NotaFiscal.data_emissao), desc(NotaFiscal.id)).limit(limit)
        notas_res = await self.db.execute(stmt_notas)
        notas = [{"data_emissao": r.data_emissao.isoformat(), "numero_nota": r.numero_nota, "valor_total": float(r.valor_total)} for r in notas_res.fetchall()]

        # 4. Top Produtos (Include quantidade_notas)
        stmt_top_prod = (
            select(
                Produto.ean, Produto.nome_limpo,
                func.sum(ItemNotaFiscal.quantidade).label("quantidade_total"),
                func.sum(ItemNotaFiscal.valor_total).label("total_gasto"),
                (func.sum(ItemNotaFiscal.valor_total) / func.nullif(func.sum(ItemNotaFiscal.quantidade), 0)).label("preco_medio"),
                func.count(func.distinct(ItemNotaFiscal.nota_fiscal_id)).label("quantidade_notas"),
            )
            .join(ItemNotaFiscal, Produto.ean == ItemNotaFiscal.ean)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id: stmt_top_prod = stmt_top_prod.where(NotaFiscal.department_id == department_id)
        if start_date: stmt_top_prod = stmt_top_prod.where(NotaFiscal.data_emissao >= start_date)
        if end_date: stmt_top_prod = stmt_top_prod.where(NotaFiscal.data_emissao <= end_date)

        stmt_top_prod = stmt_top_prod.group_by(Produto.ean, Produto.nome_limpo).order_by(desc("total_gasto")).limit(5)
        top_prod_res = await self.db.execute(stmt_top_prod)

        return {
            "fornecedor_id": str(fornecedor_id),
            "nome_exibicao": nome_exibicao,
            "resumo": {
                "total_gasto": float(total_gasto),
                "quantidade_notas": qtd_notas,
                "ticket_medio": float(ticket_medio),
                "primeira_compra": resumo_row.primeira_compra.isoformat() if resumo_row.primeira_compra else None,
                "ultima_compra": resumo_row.ultima_compra.isoformat() if resumo_row.ultima_compra else None,
            },
            "concentracao": concentracao,
            "top_produtos": [
                {
                    "ean": row.ean,
                    "nome_produto": row.nome_limpo,
                    "quantidade_total": float(row.quantidade_total),
                    "total_gasto": float(row.total_gasto),
                    "preco_medio": float(row.preco_medio or 0),
                    "quantidade_notas": row.quantidade_notas,
                } for row in top_prod_res.fetchall()
            ],
            "notas": notas
        }

    async def obter_produtos_fornecedor_export(
        self,
        fornecedor_id: UUID | str,
        department_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        if isinstance(fornecedor_id, str):
            try: fornecedor_id = UUID(fornecedor_id)
            except ValueError: return []

        stmt = (
            select(
                Produto.nome_limpo, Produto.ean,
                func.sum(ItemNotaFiscal.quantidade).label("quantidade_total"),
                (func.sum(ItemNotaFiscal.valor_total) / func.nullif(func.sum(ItemNotaFiscal.quantidade), 0)).label("preco_medio"),
                func.sum(ItemNotaFiscal.valor_total).label("total_gasto"),
                func.count(func.distinct(NotaFiscal.id)).label("frequencia_notas"),
            )
            .join(ItemNotaFiscal, Produto.ean == ItemNotaFiscal.ean)
            .join(NotaFiscal, NotaFiscal.id == ItemNotaFiscal.nota_fiscal_id)
            .where(NotaFiscal.fornecedor_id == fornecedor_id)
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id: stmt = stmt.where(NotaFiscal.department_id == department_id)
        if start_date: stmt = stmt.where(NotaFiscal.data_emissao >= start_date)
        if end_date: stmt = stmt.where(NotaFiscal.data_emissao <= end_date)

        stmt = stmt.group_by(Produto.ean, Produto.nome_limpo).order_by(desc("total_gasto")).limit(limit)
        result = await self.db.execute(stmt)
        return [
            {
                "produto": row.nome_limpo, "ean": row.ean,
                "quantidade_total": float(row.quantidade_total or 0),
                "preco_medio": float(row.preco_medio or 0),
                "total_gasto": float(row.total_gasto or 0),
                "frequencia_notas": row.frequencia_notas,
            } for row in result.fetchall()
        ]

    async def detectar_notas_duplicadas_suspeitas(
        self, department_id: UUID | None = None
    ) -> List[Dict[str, Any]]:
        subq = (
            select(
                NotaFiscal.fornecedor_id,
                NotaFiscal.data_emissao,
                NotaFiscal.valor_total,
            )
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
            .group_by(
                NotaFiscal.fornecedor_id,
                NotaFiscal.data_emissao,
                NotaFiscal.valor_total,
            )
            .having(func.count(NotaFiscal.id) > 1)
        )
        if department_id: subq = subq.where(NotaFiscal.department_id == department_id)
        subq = subq.subquery("dups")

        stmt = (
            select(
                NotaFiscal.chave_acesso,
                NotaFiscal.data_emissao,
                NotaFiscal.valor_total,
                Fornecedor.razao_social,
            )
            .join(Fornecedor, Fornecedor.id == NotaFiscal.fornecedor_id)
            .join(
                subq,
                (NotaFiscal.fornecedor_id == subq.c.fornecedor_id)
                & (NotaFiscal.data_emissao == subq.c.data_emissao)
                & (NotaFiscal.valor_total == subq.c.valor_total),
            )
            .where(NotaFiscal.status == ACTIVE_INVOICE_STATUS)
        )
        if department_id: stmt = stmt.where(NotaFiscal.department_id == department_id)

        result = await self.db.execute(stmt)
        grupos_dict = {}
        for row in result.fetchall():
            key = (row.razao_social, row.data_emissao, row.valor_total)
            if key not in grupos_dict:
                grupos_dict[key] = {
                    "fornecedor": row.razao_social,
                    "data": row.data_emissao.isoformat(),
                    "valor": float(row.valor_total),
                    "chaves": [],
                }
            grupos_dict[key]["chaves"].append(row.chave_acesso)
        return list(grupos_dict.values())
