"""Repository for procurement domain persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.compras import Fornecedor, NotaFiscal, ItemNotaFiscal, Produto, HistoricoPreco, AuditLog
from backend.schemas.internal import NotaFiscalDTO


class ProcurementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache_fornecedores = {}

    async def registrar_auditoria(
        self, 
        usuario: str, 
        operacao: str, 
        entidade: str, 
        entidade_id: str, 
        detalhes: str | None = None,
        ip: str | None = None,
        department_id: str | None = None
    ) -> None:
        """Persiste uma entrada na trilha de auditoria com isolamento de departamento."""
        log = AuditLog(
            usuario=usuario,
            operacao=operacao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhes=detalhes,
            ip_origem=ip,
            department_id=department_id
        )
        self.db.add(log)
        # Não damos flush aqui para permitir que o log suba na mesma transação da operação

    async def nota_existe(self, chave_acesso: str) -> bool:
        stmt = select(NotaFiscal.id).where(NotaFiscal.chave_acesso == chave_acesso)
        result = await self.db.execute(stmt)
        return result.fetchone() is not None

    async def obter_categorias_unicas(self) -> list[str]:
        """Retorna uma lista de categorias distintas existentes no catálogo."""
        stmt = select(Produto.categoria).distinct().where(Produto.categoria != None)
        res = await self.db.execute(stmt)
        return [c for c in res.scalars() if c and c != "Não Classificado"]

    async def salvar_nota_completa(self, chave_acesso: str, dto: NotaFiscalDTO, department_id: str | None = None) -> NotaFiscal:
        # 1. Obter Fornecedor (usa cache local de sessão se necessário)
        fornecedor = await self._obter_ou_criar_fornecedor(dto.fornecedor)
        
        # 2. Bulk Lookup de Produtos Existentes para evitar N+1
        eans_na_nota = list({item.codigo_produto for item in dto.itens})
        stmt_produtos = select(Produto).where(Produto.ean.in_(eans_na_nota))
        res_produtos = await self.db.execute(stmt_produtos)
        produtos_map = {p.ean: p for p in res_produtos.scalars()}

        # 3. Nota Fiscal
        nota = NotaFiscal(
            fornecedor_id=fornecedor.id,
            department_id=department_id,
            numero_nota=dto.numero_nota,
            chave_acesso=chave_acesso,
            data_emissao=dto.data_emissao,
            valor_total=dto.valor_total,
        )
        self.db.add(nota)
        await self.db.flush()

        # 4. Itens e Produtos
        for item_dto in dto.itens:
            # Recupera do map ou cria novo
            produto = produtos_map.get(item_dto.codigo_produto)
            if not produto:
                produto = Produto(
                    ean=item_dto.codigo_produto,
                    nome_limpo=item_dto.descricao,
                    marca=item_dto.marca,
                    categoria=item_dto.categoria or "Não Classificado",
                    unidade="un"
                )
                self.db.add(produto)
                produtos_map[produto.ean] = produto 
            
            item_fiscal = ItemNotaFiscal(
                nota_fiscal_id=nota.id,
                ean=produto.ean,
                descricao_original=item_dto.descricao,
                quantidade=item_dto.quantidade,
                valor_unitario=item_dto.valor_unitario,
                valor_total=item_dto.valor_total,
                categoria_sugerida=item_dto.categoria,
                categoria_sugerida_origem=item_dto.categoria_sugerida_origem,
                categoria_sugerida_confidence=item_dto.categoria_sugerida_confidence,
                categoria_sugerida_modelo=item_dto.categoria_sugerida_modelo,
            )
            self.db.add(item_fiscal)

            # 5. Histórico de Preço
            historico = HistoricoPreco(
                ean=produto.ean,
                nota_fiscal_id=nota.id,
                item_nota_fiscal=item_fiscal,
                data_compra=dto.data_emissao,
                local=fornecedor.razao_social,
                preco_pago=item_dto.valor_unitario,
                quantidade=item_dto.quantidade,
            )
            self.db.add(historico)

        await self.db.flush()
        return nota

    async def _obter_ou_criar_fornecedor(self, dto) -> Fornecedor:
        if dto.cnpj in self._cache_fornecedores:
            return self._cache_fornecedores[dto.cnpj]
            
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
        
        self._cache_fornecedores[dto.cnpj] = fornecedor
        return fornecedor
