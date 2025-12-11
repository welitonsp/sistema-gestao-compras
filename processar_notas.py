import os
import shutil
from pathlib import Path

from ia_groq_utils import criar_tabelas_se_nao_existirem
from importar_pdf import importar_pdf_direto

# ==========================================
# 0. CONFIGURAÇÃO DE PASTAS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
PASTA_NOVAS = BASE_DIR / "NOVAS_NOTAS"
PASTA_PROCESSADAS = BASE_DIR / "PROCESSADAS"

# Garante que as pastas existam
PASTA_NOVAS.mkdir(exist_ok=True)
PASTA_PROCESSADAS.mkdir(exist_ok=True)


# ==========================================
# 1. PROCESSAMENTO EM LOTE
# ==========================================

def listar_pdfs_novos():
    """
    Lista todos os arquivos .pdf na pasta NOVAS_NOTAS.
    """
    return sorted(PASTA_NOVAS.glob("*.pdf"))


def processar_pdfs_em_lote():
    """
    Processa todos os PDFs que estiverem na pasta NOVAS_NOTAS,
    chamando o importar_pdf_direto para cada um e depois
    movendo o arquivo para a pasta PROCESSADAS.
    """
    print("\n" + "=" * 60)
    print("📂 PROCESSAMENTO EM LOTE - PASTA NOVAS_NOTAS")
    print("=" * 60)

    # Garante estrutura do banco
    criar_tabelas_se_nao_existirem()

    pdfs = listar_pdfs_novos()
    if not pdfs:
        print("⚠️ Nenhum arquivo .pdf encontrado em NOVAS_NOTAS.")
        print(f"   Coloque as notas em: {PASTA_NOVAS}")
        return

    print(f"✅ {len(pdfs)} arquivo(s) PDF encontrado(s) para processamento.\n")

    processados_com_sucesso = 0

    for pdf_path in pdfs:
        print("\n" + "-" * 60)
        print(f"➡️  Processando arquivo: {pdf_path.name}")
        print("-" * 60)

        try:
            importar_pdf_direto(str(pdf_path))
            processados_com_sucesso += 1

            # Move o arquivo para a pasta PROCESSADAS
            destino = PASTA_PROCESSADAS / pdf_path.name
            shutil.move(str(pdf_path), str(destino))
            print(f"📦 Arquivo movido para: {destino}")

        except Exception as e:
            print(f"❌ Erro ao processar {pdf_path.name}: {e}")
            print("   O arquivo será mantido em NOVAS_NOTAS para análise posterior.")
            continue

    print("\n" + "=" * 60)
    print(f"🏁 FIM DO PROCESSO: {processados_com_sucesso} arquivo(s) processado(s) com sucesso.")
    print("=" * 60)


# ==========================================
# 2. PONTO DE ENTRADA
# ==========================================

if __name__ == "__main__":
    print("📊 SISTEMA DE GESTÃO DE COMPRAS - PROCESSADOR DE NOTAS (PDF)")
    processar_pdfs_em_lote()
    print("\n✨ Processo finalizado.")
