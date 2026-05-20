# main.py
# ==========================================================
# GESTAOCOMPRAS - ORQUESTRADOR PRINCIPAL DO SISTEMA (V2)
# ==========================================================

import os
import sys
import asyncio
from pathlib import Path

# Garante execução a partir da raiz
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.logger import get_logger

logger = get_logger("main")

def menu():
    print("\n" + "=" * 80)
    print(" 📊 GESTAOCOMPRAS - SISTEMA INTELIGENTE (MODO UNIFICADO)")
    print("=" * 80)
    print("  1 - [SISTEMA] Resetar Banco de Dados (Zerar Tudo)")
    print("  2 - [IMPORT ] Importar Nota Fiscal (PDF)")
    print("  3 - [IMPORT ] Importar Compras Manualmente (CLI)")
    print("  4 - [IMPORT ] Processar XML (NFe/NFCe/CFe)")
    print("  5 - [LOTE   ] Processar todos os PDFs da pasta NOVAS_NOTAS")
    print("  6 - [REPORT ] Ver Gastos por Categoria")
    print("  7 - [REPORT ] Ver Últimos Lançamentos (Nuvem)")
    print("  8 - [INSIGHT] Ver Alertas de Preço (Anomalias)")
    print("  9 - [DEBUG  ] Testar Ambiente e IA (Groq)")
    print("  10- [IMPORT ] Buscar NFC-e (SEFAZ GO) por Chave")
    print("  0 - Sair")
    print("=" * 80)
    return input("Escolha uma opção: ").strip()

async def executar_opcao(opcao):
    try:
        if opcao == "1":
            import reset_tabelas
            await reset_tabelas.reset_database()

        elif opcao == "2":
            import importar_pdf
            await importar_pdf.main()

        elif opcao == "3":
            import importar_manual
            await importar_manual.main()

        elif opcao == "4":
            import importador_cfe
            await importador_cfe.main()

        elif opcao == "5":
            import processar_notas
            await processar_notas.processar_pdfs_em_lote()

        elif opcao == "6":
            import ver_relatorio_categorias
            total, resumo = await ver_relatorio_categorias.obter_dados_relatorio()
            ver_relatorio_categorias.exibir_relatorio(total, resumo)

        elif opcao == "7":
            import ver_relatorio_nuvem
            await ver_relatorio_nuvem.mostrar_dados()

        elif opcao == "8":
            import ver_alertas_preco
            await ver_alertas_preco.exibir_alertas()

        elif opcao == "9":
            import test_env
            import testar_groq
            test_env.main()

        elif opcao == "10":
            chave = input("Digite a chave de 44 dígitos: ").strip()
            if len(chave) == 44:
                from backend.core.database import SessionLocal
                from backend.services.importador_sefaz import ImportadorSefazService
                async with SessionLocal() as session:
                    async with ImportadorSefazService(session) as service:
                        await service.importar_por_chave(chave)
                        print("✅ Nota importada com sucesso via SEFAZ!")
            else:
                print("❌ Chave inválida.")

        elif opcao == "0":
            return False

        else:
            print("\n⚠️ Opção inválida.")

    except Exception as exc:
        logger.error(f"Erro na execução da opção {opcao}: {exc}", exc_info=True)
        print(f"\n❌ ERRO: {exc}")
    
    return True

async def main():
    logger.info("Main menu started.")
    print("\nBem-vindo ao Gestão Compras V2.0")
    
    continuar = True
    while continuar:
        opcao = menu()
        continuar = await executar_opcao(opcao)

    print("\nEncerrando o sistema. Até logo!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
