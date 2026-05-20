import asyncio
from backend.core.database import engine
from backend.models.base import Base
from core.logger import get_logger

logger = get_logger("reset_db")

async def reset_database():
    print("⚠️  AVISO: Isso irá apagar TODAS as tabelas do banco de dados.")
    confirmacao = input("Deseja continuar? (s/N): ").strip().lower()
    
    if confirmacao != 's':
        print("Cancelado.")
        return

    async with engine.begin() as conn:
        print("🗑️  Apagando tabelas...")
        await conn.run_sync(Base.metadata.drop_all)
        print("🏗️  Recriando tabelas...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Banco de dados resetado com sucesso!")

if __name__ == "__main__":
    asyncio.run(reset_database())
