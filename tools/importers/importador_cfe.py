import asyncio
import sys
from pathlib import Path
from backend.core.database import SessionLocal
from backend.services.repository import ProcurementRepository
from backend.services.xml_processor import XMLProcessorService

async def main():
    if len(sys.argv) < 2:
        print("Uso: python importador_cfe.py <caminho_do_xml_ou_chave>")
        # Se não passar nada, poderíamos perguntar a chave ou listar arquivos
        xml_files = list(Path(".").glob("*.xml"))
        if not xml_files:
            print("Nenhum arquivo XML encontrado na pasta atual.")
            return
        xml_path = xml_files[0]
    else:
        arg = sys.argv[1]
        xml_path = Path(arg)
        if not xml_path.exists() and len(arg) == 44:
            # É uma chave, tenta buscar no cache/sefaz se implementado
            print(f"Buscando XML pela chave: {arg}...")
            # Aqui poderíamos integrar o resolver_xml_por_chave_goias se necessário
            # Mas por simplicidade, vamos focar em arquivos locais primeiro.
            print("Funcionalidade de busca remota deve ser usada via API.")
            return

    if not xml_path.exists():
        print(f"❌ Arquivo não encontrado: {xml_path}")
        return

    async with SessionLocal() as session:
        repo = ProcurementRepository(session)
        service = XMLProcessorService(repo)

        print(f"🚀 Importando XML: {xml_path.name}...")
        sucesso = await service.processar_arquivo(xml_path)
        
        if sucesso:
            print("✅ Importação concluída com sucesso!")
        else:
            print("❌ Falha na importação. Verifique os logs.")

if __name__ == "__main__":
    asyncio.run(main())
