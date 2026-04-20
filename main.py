# main.py
# ==========================================================
# GESTAOCOMPRAS - ORQUESTRADOR PRINCIPAL DO SISTEMA
# ==========================================================
# Este e o ponto unico de entrada do sistema.
# Ele orquestra:
# - pipelines (execucao)
# - services (IA / inteligencia)
# - utilitarios e relatorios
# ==========================================================

import os
import sys

from core.logger import get_logger

# ----------------------------------------------------------
# GARANTE EXECUCAO A PARTIR DA RAIZ DO PROJETO
# ----------------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logger = get_logger("main")


# ----------------------------------------------------------
# MENU
# ----------------------------------------------------------

def menu():
    print("\n" + "=" * 80)
    print("GESTAOCOMPRAS - SISTEMA INTELIGENTE DE GESTAO DE COMPRAS")
    print("=" * 80)
    print("1  - Resetar banco de dados (CUIDADO)")
    print("2  - Importar nota fiscal (PDF)")
    print("3  - Importar compras manualmente (TXT)")
    print("4  - Processar XML NFC-e (pipeline completo)")
    print("5  - Classificar produtos pendentes (IA Groq)")
    print("6  - Relatorio: gastos por categoria")
    print("7  - Relatorio: ultimos lancamentos")
    print("8  - Testar ambiente (.env)")
    print("9  - Testar conexao com Groq")
    print("10 - Gerar insights inteligentes (Gemini)")
    print("11 - Importar NFC-e/CF-e (SEFAZ GO) por chave")
    print("0  - Sair")
    print("=" * 80)
    return input("Escolha uma opcao: ").strip()


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
                import testar_groq  # noqa: F401

            elif opcao == "10":
                from services.gemini_insights import main as gemini_insights_main

                gemini_insights_main()

            elif opcao == "11":
                import importador_cfe

                importador_cfe.main()

            elif opcao == "0":
                logger.info("Encerrando sistema")
                print("\nEncerrando o sistema GestaoCompras.")
                sys.exit(0)

            else:
                print("\nOpcao invalida.")

        except Exception as exc:
            logger.exception("Erro durante execucao")
            print("\nERRO DURANTE A EXECUCAO")
            print("-" * 80)
            print(str(exc))
            print("-" * 80)


# ----------------------------------------------------------
# ENTRYPOINT
# ----------------------------------------------------------

if __name__ == "__main__":
    main()
