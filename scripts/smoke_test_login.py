import asyncio
import httpx
from backend.main import app

async def test_real_login():
    print("🔐 Iniciando Smoke Test de Autenticação...")
    
    # Usamos o ASGITransport para testar a app sem subir um servidor real
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Tenta o login com o usuário criado no bootstrap
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "admin",
                "password": "admin123"
            }
        )
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ LOGIN REALIZADO COM SUCESSO!")
            print(f"🎫 Token Gerado: {token_data['access_token'][:50]}...")
            
            # Testa acesso a uma rota protegida com o token recebido
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            res_health = await client.get("/api/v1/dashboard/resumo", headers=headers)
            
            if res_health.status_code == 200:
                print("✅ ACESSO AO DASHBOARD AUTORIZADO (RBAC OK)!")
            else:
                print(f"❌ FALHA NO ACESSO: {res_health.status_code} - {res_health.text}")
        else:
            print(f"❌ FALHA NO LOGIN: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(test_real_login())
