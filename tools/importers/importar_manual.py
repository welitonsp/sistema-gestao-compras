import asyncio
import os
from datetime import datetime
from pathlib import Path

from backend.core.database import SessionLocal
from backend.services.repository import ProcurementRepository
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.manual_import import ManualImportService

async def main():
    print("\n📊 SISTEMA DE GESTÃO DE COMPRAS - IMPORTAÇÃO MANUAL (CLI)")
    print("-" * 60)

    # 1. Coleta de dados Faltantes (Interativo)
    data_str = input("➡️ Digite a Data da Compra (AAAA-MM-DD) [Hoje]: ").strip()
    if not data_str:
        data_compra = datetime.now().date()
    else:
        try:
            data_compra = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            print("❌ Formato de data inválido. Use AAAA-MM-DD.")
            return

    mercado = input("➡️ Digite o Nome do Mercado: ").strip()
    if not mercado:
        print("❌ O nome do mercado é obrigatório.")
        return

    caminho_arquivo = input("➡️ Digite o nome do arquivo TXT [manual_extract.txt]: ").strip() or "manual_extract.txt"

    if not os.path.exists(caminho_arquivo):
        print(f"❌ Arquivo não encontrado: {caminho_arquivo}")
        return

    # 2. Leitura das linhas
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        linhas = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('Num.')]

    if not linhas:
        print("⚠️ Nenhuma linha de dados encontrada no arquivo.")
        return

    # 3. Inicialização dos Serviços Modernos
    async with SessionLocal() as db:
        repo = ProcurementRepository(db)
        ai = AIStructuredExtractor()
        servico = ManualImportService(repo, ai)

        # 4. Processamento
        processados = await servico.processar_texto_manual(linhas, data_compra, mercado)

        # 5. Commit final (A transação interna do repositório pode fazer commit, 
        # mas aqui garantimos o fechamento da sessão)
        await db.commit()

    print(f"\n🏁 IMPORTAÇÃO FINALIZADA!")
    print(f"   Total de itens processados: {processados}")
    print(f"   Dados salvos no banco: {os.getenv('DATABASE_URL').split('@')[-1]}") # Esconde credenciais

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Operação cancelada pelo usuário.")
    except Exception as e:
        print(f"\n❌ Ocorreu um erro inesperado: {e}")