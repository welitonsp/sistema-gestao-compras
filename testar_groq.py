from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ ERRO: Chave do Groq não encontrada no arquivo .env")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)

try:
    print("🔍 Testando conexão com Groq...")
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Você é um assistente técnico que responde apenas com dados válidos."},
            {"role": "user", "content": "Qual é o seu modelo?"}
        ],
        max_tokens=10,
        temperature=0.1
    )
    
    resposta = response.choices[0].message.content.strip()
    print(f"✅ CONEXÃO BEM SUCEDIDA!")
    print(f"🤖 Modelo: llama-3.1-8b-instant")
    print(f"💬 Resposta: '{resposta}'")
    print("\n🎉 SUA CHAVE DO GROQ ESTÁ FUNCIONANDO PERFEITAMENTE!")
    
except Exception as e:
    print(f"❌ FALHA NA CONEXÃO: {str(e)}")
    print("\n🔍 Possíveis causas:")
    print("1. Chave inválida ou expirada")
    print("2. Modelo incorreto (verifique em https://console.groq.com/docs/models)")
    print("3. Limite de requisições excedido (reset diário)")
    exit(1)