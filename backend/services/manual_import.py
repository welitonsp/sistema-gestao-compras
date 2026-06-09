"""Service for manual procurement data entry."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import List

from backend.services.ai_processor import AIStructuredExtractor
from backend.services.repository import ProcurementRepository
from backend.schemas.internal import FornecedorDTO, ItemNotaDTO, NotaFiscalDTO


class ManualImportService:
    def __init__(self, repo: ProcurementRepository, ai_extractor: AIStructuredExtractor):
        self.repo = repo
        self.ai = ai_extractor

    async def processar_texto_manual(
        self,
        linhas: List[str],
        data_compra: date,
        mercado: str,
        department_id=None,
    ):
        """Processa linhas de um extrato manual e salva no banco de forma resiliente."""
        
        print(f"📦 Processando {len(linhas)} itens manuais...")
        
        # Agrupamos para processar (futuramente poderíamos enviar em lote para a IA)
        processados = 0
        for linha in linhas:
            # Lógica de extração simplificada (pode ser melhorada com IA se a linha for complexa)
            # Aqui mantemos a compatibilidade com a lógica de split do usuário
            partes = linha.split()
            if len(partes) < 2:
                continue

            try:
                valor_total = Decimal(partes[-1].replace(',', '.'))
                # Tenta pegar a Qtd (é o terceiro valor de trás para frente)
                try:
                    quantidade = Decimal(partes[-3].replace(',', '.'))
                except:
                    quantidade = Decimal("1.0")

                descricao_original = " ".join(partes[1:-3])
                if not descricao_original:
                    continue
                
                valor_unitario = valor_total / quantidade if quantidade > 0 else Decimal("0.0")

                # Gera EAN determinístico para itens manuais (Melhor prática: Hash estável)
                ean_manual = f"MAN_{abs(hash(descricao_original))}"

                # Usa a IA para classificar o produto individualmente (ou busca no catálogo)
                # Como é manual, fazemos um de cada vez para garantir precisão
                dados_ia = await self.ai.classificar_item_manual(
                    descricao_original,
                    department_id=department_id,
                )
                
                # Criamos um DTO de Nota Fiscal "Fake" para usar o repositório unificado
                # Isso garante que a lógica de "Obter ou Criar Fornecedor/Produto" seja idêntica
                item_dto = ItemNotaDTO(
                    ean=ean_manual,
                    descricao=descricao_original,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total
                )

                # Persistência via Repositório (Garante Catálogo + Histórico)
                async with self.repo.db.begin():
                    # No modo manual, criamos/atualizamos o produto
                    produto = await self.repo._obter_ou_criar_produto(item_dto)
                    
                    # Atualiza os dados da IA se o produto for novo ou "Não Classificado"
                    if produto.categoria == "Não Classificado":
                        produto.nome_limpo = dados_ia.get("produto", descricao_original)
                        produto.marca = dados_ia.get("marca")
                        produto.categoria = dados_ia.get("categoria", "Outros")
                        produto.unidade = dados_ia.get("unidade", "un")

                    # Salva no histórico de preços
                    await self.repo.db.execute(
                        self.repo.db.add(
                            self.repo.models.HistoricoPreco(
                                ean=produto.ean,
                                data_compra=data_compra,
                                local=mercado,
                                preco_pago=valor_unitario,
                                quantidade=quantidade
                            )
                        )
                    )
                
                processados += 1
                print(f"   ✅ [{processados}] {descricao_original[:30]}...")

            except Exception as e:
                print(f"   ❌ Erro na linha: {linha[:50]}... | {e}")
                continue

        return processados
