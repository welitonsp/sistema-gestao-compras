import httpx
import asyncio

async def test_resumo():
    chave = "52260517457404001183655110000409351275118105"
    url = f"https://nfeweb.sefaz.go.gov.br/nfeweb/sites/nfce/resumoNFCe?p={chave}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        print(f"Tentando Resumo: {url}")
        try:
            resp = await client.get(url, headers=headers)
            print(f"Status: {resp.status_code} | Tamanho: {len(resp.text)}")
            if "chave" in resp.text.lower() and len(resp.text) > 2000:
                print("✅ ENCONTROU PÁGINA COM DADOS!")
            else:
                print("❌ Falhou ou retornou página de erro.")
        except Exception as e:
            print(f"💥 Erro: {e}")

if __name__ == "__main__":
    asyncio.run(test_resumo())
