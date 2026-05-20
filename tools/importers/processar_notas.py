import os
import shutil
import asyncio
from pathlib import Path

from backend.core.database import SessionLocal
from backend.services.repository import ProcurementRepository
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.pdf_processor import PDFProcessorService
from core.logger import get_logger

logger = get_logger("batch_pdf")

# ==========================================
# CONFIGURAÇÃO DE PASTAS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
PASTA_NOVAS = BASE_DIR / "NOVAS_NOTAS"
PASTA_PROCESSADAS = BASE_DIR / "PROCESSADAS"

PASTA_NOVAS.mkdir(exist_ok=True)
PASTA_PROCESSADAS.mkdir(exist_ok=True)


async def processar_pdfs_em_lote():
    """
    Processa todos os PDFs que estiverem na pasta NOVAS_NOTAS de forma assíncrona.
    """
    logger.info("Iniciando processamento em lote de PDFs.")
    
    pdfs = sorted(PASTA_NOVAS.glob("*.pdf"))
    if not pdfs:
        print("⚠️ Nenhum arquivo .pdf encontrado em NOVAS_NOTAS.")
        return

    print(f"✅ {len(pdfs)} arquivo(s) PDF encontrado(s).\n")

    async with SessionLocal() as session:
        repo = ProcurementRepository(session)
        ai = AIStructuredExtractor()
        service = PDFProcessorService(repo, ai)

        processados_com_sucesso = 0

        for pdf_path in pdfs:
            print(f"➡️  Processando: {pdf_path.name}...", end=" ", flush=True)
            
            sucesso = await service.processar_arquivo(pdf_path)
            
            if sucesso:
                processados_com_sucesso += 1
                destino = PASTA_PROCESSADAS / pdf_path.name
                # Tenta mover, se o destino já existir, renomeia
                if destino.exists():
                    destino = PASTA_PROCESSADAS / f"{pdf_path.stem}_{int(asyncio.get_event_loop().time())}{pdf_path.suffix}"
                
                shutil.move(str(pdf_path), str(destino))
                print("✅ OK")
            else:
                print("❌ FALHA (Veja os logs)")

    print(f"\n🏁 FIM: {processados_com_sucesso} processados com sucesso.")


if __name__ == "__main__":
    asyncio.run(processar_pdfs_em_lote())
