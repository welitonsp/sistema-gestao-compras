"""Repository for procurement domain persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import Fornecedor, NotaFiscal, ItemNotaFiscal, Produto, HistoricoPreco
from backend.schemas.internal import NotaFiscalDTO


class ProcurementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def nota_existe(self, chave_acesso: str) -> bool:
        stmt = select(NotaFiscal.id).where(NotaFiscal.chave_acesso == chave_acesso)
        result = await self.db.execute(stmt)
        return result.fetchone() is not None

    async def salvar_nota_completa(self, chave_acesso: str, dto: NotaFiscalDTO) -> NotaFiscal:
        async with self.db.begin_nested():
            # 1. Fornecedor
            fornecedor = await self._obter_ou_criar_fornecedor(dto.fornecedor)
            
            # 2. Nota Fiscal
            nota = NotaFiscal(
                fornecedor_id=fornecedor.id,
                numero_nota=dto.numero_nota,
                chave_acesso=chave_acesso,
                data_emissao=dto.data_emissao,
                valor_total=dto.valor_total,
            )
            self.db.add(nota)
            await self.db.flush()

            # 3. Itens e Produtos
            for item_dto in dto.itens:
                produto = await self._obter_ou_criar_produto(item_dto)
                
                item_fiscal = ItemNotaFiscal(
                    nota_fiscal_id=nota.id,
                    ean=produto.ean,
                    descricao_original=item_dto.descricao,
                    quantidade=item_dto.quantidade,
                    valor_unitario=item_dto.valor_unitario,
                    valor_total=item_dto.valor_total,
                )
                self.db.add(item_fiscal)

                # 4. Histórico de Preço (Espelho para consultas rápidas)
                historico = HistoricoPreco(
                    ean=produto.ean,
                    data_compra=dto.data_emissao,
                    local=fornecedor.razao_social,
                    preco_pago=item_dto.valor_unitario,
                    quantidade=item_dto.quantidade,
                )
                self.db.add(historico)

            await self.db.flush()
            return nota

    async def _obter_ou_criar_fornecedor(self, dto) -> Fornecedor:
        stmt = select(Fornecedor).where(Fornecedor.cnpj == dto.cnpj)
        fornecedor = await self.db.scalar(stmt)
        if not fornecedor:
            fornecedor = Fornecedor(
                cnpj=dto.cnpj,
                razao_social=dto.razao_social,
                nome_fantasia=dto.nome_fantasia
            )
            self.db.add(fornecedor)
            await self.db.flush()
        return fornecedor

    async def _obter_ou_criar_produto(self, item_dto) -> Produto:
        stmt = select(Produto).where(Produto.ean == item_dto.codigo_produto)
        produto = await self.db.scalar(stmt)
        if not produto:
            # Aqui no futuro poderíamos chamar uma IA específica para 
            # categorizar o produto CANÔNICO se ele for novo.
            produto = Produto(
                ean=item_dto.codigo_produto,
                nome_limpo=item_dto.descricao, # Inicialmente usa a descrição da nota
                categoria="Não Classificado",
                unidade="un"
            )
            self.db.add(produto)
            await self.db.flush()
        return produto
