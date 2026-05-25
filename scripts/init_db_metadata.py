import asyncio
from backend.core.database import engine
from backend.models.base import Base
from backend.models.compras import AuditLog # Garante que os modelos estão carregados

async def init_db():
    print("🛠️  Sincronizando metadados com o banco de dados...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de dados atualizado.")

if __name__ == "__main__":
    asyncio.run(init_db())
