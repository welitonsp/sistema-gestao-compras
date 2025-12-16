# main.py
# ==========================================================
# GESTAOCOMPRAS — ORQUESTRADOR PRINCIPAL DO SISTEMA
# ==========================================================
# Este é o ponto único de entrada do sistema.
# Ele orquestra:
# - pipelines (execução)
# - services (IA / inteligência)
# - utilitários e relatórios
#
# Arquivo completo, didático e estável.
# ==========================================================

import sys
import os

# ----------------------------------------------------------
# GARANTE EXECUÇÃO A PARTIR DA RAIZ DO PROJETO
# ----------------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.logger import get_logger

logger = get_logger("main")


# ----------------------------------------------------------
# MENU
# ----------------------------------------------------------

def menu():
    print("\n" + "=" * 80)
    print("🛒 GESTAOCOMPRAS — SISTEMA INTELIGENTE DE GESTÃO DE COMPRAS")
    print("=" * 80)
    print("1  - Resetar banco de dados (CUIDADO)")
    print("2  - Importar nota fiscal (PDF)")
    print("3  - Importar compras manualmente (TXT)")
    print("4  - Processar XML NFC-e (pipeline completo)")
    print("5  - Classificar produtos pendentes (IA Groq)")
    print("6  - Relatório: gastos por categoria")
    print("7  - Relatório: últimos lançamentos")
    print("8  - Testar ambiente (.env)")
    print("9  - Testar conexão com Groq")
    print("10 - Gerar insights inteligentes (Gemini)")
    print("0  - Sair")
    print("=" * 80)
    return input("Escolha uma opção: ").strip()


# ----------------------------------------------------------
# MAIN LOOP
# ----------------------------------------------------------

def main():
    logger.info("Sistema GestaoCompras iniciado")

    while True:
        opcao = menu()

        try:
            if opcao == "1":
                logger.warning("Reset de banco solicitado")
                import reset_tabelas
                reset_tabelas.main()

            elif opcao == "2":
                from pipelines.importar_pdf import executar
                caminho = input("Informe o caminho do PDF: ").strip()
                executar(caminho)

            elif opcao == "3":
                from pipelines.importar_manual import executar
                caminho = input("Informe o caminho do TXT: ").strip()
                executar(caminho)

            elif opcao == "4":
                import sistema_completo
                sistema_completo.main()

            elif opcao == "5":
                from classificar_produtos_ia import classificar_produtos_pendentes
                classificar_produtos_pendentes()

            elif opcao == "6":
                import ver_relatorio_categorias
                ver_relatorio_categorias.main()

            elif opcao == "7":
                import ver_relatorio_nuvem
                ver_relatorio_nuvem.mostrar_dados()

            elif opcao == "8":
                import test_env
                test_env.main()

            elif opcao == "9":
                import testar_groq

            elif opcao == "10":
                from services.gemini_insights import main as gemini_insights_main
                gemini_insights_main()

            elif opcao == "0":
                logger.info("Encerrando sistema")
                print("\n👋 Encerrando o sistema GestaoCompras.")
                sys.exit(0)

            else:
                print("\n⚠️ Opção inválida.")

        except Exception as e:
            logger.exception("Erro durante execução")
            print("\n❌ ERRO DURANTE A EXECUÇÃO")
            print("-" * 80)
            print(str(e))
            print("-" * 80)


# ----------------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------------

if __name__ == "__main__":
    main()
