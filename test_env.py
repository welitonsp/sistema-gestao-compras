# test_env.py
# Teste simples para verificar se o .env está sendo lido corretamente.

import os
from dotenv import load_dotenv

def main():
    print("📁 Pasta atual:", os.getcwd())

    if os.path.exists(".env"):
        print("✅ Arquivo .env encontrado nesta pasta.")
    else:
        print("❌ Arquivo .env NÃO encontrado na pasta atual!")

    print("\n🔄 Carregando variáveis do .env...")
    load_dotenv()

    variaveis = [
        "GROQ_API_KEY",
        "LLAMA_API_KEY",
        "DATABASE_URL",
        "GEMINI_API_KEY",  # só pra ver se ainda existe
    ]

    print("\n🔑 Resultado da leitura das variáveis:\n")
    for nome in variaveis:
        valor = os.getenv(nome)
        if valor:
            if len(valor) > 12:
                exibicao = valor[:6] + "..." + valor[-4:]
            else:
                exibicao = valor
            print(f"  • {nome} = {exibicao} (OK)")
        else:
            print(f"  • {nome} = (não definida)")

if __name__ == "__main__":
    main()
