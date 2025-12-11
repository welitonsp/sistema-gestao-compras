# reset_tabelas.py
# Apaga as tabelas produtos e historico_precos no Neon
# para que possam ser recriadas pelo processar_notas.py (versão nova).

import os
import psycopg2
from dotenv import load_dotenv

# Carrega .env (onde está o DATABASE_URL)
load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL não configurado no .env")

print("Conectando ao banco Neon...")
conn = psycopg2.connect(database_url)
cur = conn.cursor()

print("Apagando tabelas historico_precos e produtos (se existirem)...")
cur.execute("DROP TABLE IF EXISTS historico_precos;")
cur.execute("DROP TABLE IF EXISTS produtos;")

conn.commit()
cur.close()
conn.close()
print("✅ Tabelas apagadas com sucesso.")
print("Agora rode novamente: python processar_notas.py")
