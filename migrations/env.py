import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Adiciona o diretório raiz ao path para importar o backend
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.config import settings
from backend.models.base import Base
# Importa modelos para garantir registro no metadata
from backend.models.compras import Fornecedor, NotaFiscal, ItemNotaFiscal, Produto, HistoricoPreco, AuditLog, ClassificacaoCache, CanonizacaoProduto

config = context.config

# Sobrescreve a URL do banco com a do sistema (convertendo asyncpg para psycopg2 se necessário)
db_url = settings.database_url
if db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

# Remove parâmetros de query que podem bugar o psycopg2 (ex: ssl=true em drivers async)
if "?" in db_url:
    base_url, query = db_url.split("?", 1)
    # Mantém apenas o que o psycopg2 entende ou remove o que causa erro
    # Para o Neon, geralmente sslmode=require é seguro
    db_url = base_url + "?sslmode=require"

config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
