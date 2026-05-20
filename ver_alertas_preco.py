import asyncio
from backend.core.database import SessionLocal
from backend.services.insights_processor import PriceInsightsService
from ver_relatorio_categorias import formatar_moeda

async def exibir_alertas():
    async with SessionLocal() as session:
        service = PriceInsightsService(session)
        alertas = await service.detectar_variacoes_anomalas(threshold_percent=10.0)
        
        print("\n" + "=" * 80)
        print("🚨 ALERTAS DE VARIAÇÃO DE PREÇO (INSIGHTS)")
        print("=" * 80)
        
        if not alertas:
            print("✅ Nenhum produto com variação significativa detectado.")
            return

        print(f"{'PRODUTO':<30} | {'MÉDIA':>10} | {'ATUAL':>10} | {'VAR%':>8} | {'LOCAL'}")
        print("-" * 80)

        for a in alertas:
            cor = "🔴" if a["variacao_percentual"] > 0 else "🟢"
            print(f"{a['produto'][:30]:<30} | {formatar_moeda(a['preco_medio']):>10} | {formatar_moeda(a['preco_atual']):>10} | {cor} {a['variacao_percentual']:+6.1f}% | {a['local']}")

        print("-" * 80)
        print("Média móvel calculada sobre o histórico total de compras.")
        print("=" * 80 + "\n")

async def main():
    try:
        await exibir_alertas()
    except Exception as e:
        print(f"❌ Erro ao exibir alertas: {e}")

if __name__ == "__main__":
    asyncio.run(main())
