import asyncio
import sys
from pathlib import Path
from backend.core.database import SessionLocal
from backend.services.repository import ProcurementRepository
from backend.services.ai_processor import AIStructuredExtractor
from backend.services.pdf_processor import PDFProcessorService

async def main():
    if len(sys.argv) < 2:
        print("Uso: python importar_pdf.py <caminho_do_pdf>")
        # Se não passar nada, usa o arquivo padrão para demonstração
        pdf_path = Path("NOVAS_NOTAS/7f5456c3-b0b5-4834-a85c-6872084f1a38.pdf")
        if not pdf_path.exists():
             # Fallback para o que estava antes
             pdf_path = Path("b5c8f464-ba83-4a53-88d4-2667ea9896e9.pdf")
    else:
        pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"❌ Arquivo não encontrado: {pdf_path}")
        return

    async with SessionLocal() as session:
        repo = ProcurementRepository(session)
        ai = AIStructuredExtractor()
        service = PDFProcessorService(repo, ai)

        print(f"🚀 Importando PDF: {pdf_path.name}...")
        sucesso = await service.processar_arquivo(pdf_path)
        
        if sucesso:
            print("✅ Importação concluída com sucesso!")
        else:
            print("❌ Falha na importação. Verifique os logs.")

if __name__ == "__main__":
    asyncio.run(main())
