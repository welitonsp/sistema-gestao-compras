# Script para gerar o arquivo .env corretamente
conteudo = """GEMINI_API_KEY="AIzaSyA7f0AvKx8QLheZJoVT8hz_Dgvdfb74T9s"
DATABASE_URL="postgresql://neondb_owner:npg_VQHlgL86DrzX@ep-mute-bird-ae51yoy2-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
"""

try:
    with open(".env", "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    print("✅ SUCESSO! O arquivo .env foi criado corretamente.")
    print("Agora você pode rodar o sistema_completo.py")
except Exception as e:
    print(f"❌ Erro ao criar arquivo: {e}")