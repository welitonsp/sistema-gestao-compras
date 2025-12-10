import psycopg2

# --- FUNÇÃO PARA LER A SENHA DO ARQUIVO .ENV ---
def ler_credenciais():
    link_banco = None
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for linha in f:
                if "DATABASE_URL" in linha and "=" in linha:
                    # Pega tudo depois do primeiro igual e limpa aspas/espaços
                    link_banco = linha.split("=", 1)[1].strip().strip('"').strip("'")
    except:
        print("❌ Erro: Não consegui ler o arquivo .env")
    return link_banco

# --- VISUALIZADOR ---
def mostrar_dados():
    link = ler_credenciais()
    if not link:
        print("❌ ERRO: Link do banco não encontrado no .env")
        return

    try:
        print("🔌 Conectando ao Neon para baixar relatório...")
        conn = psycopg2.connect(link)
        cursor = conn.cursor()

        # 1. Relatório de Categorização (O Trabalho da IA)
        print("\n" + "="*85)
        print(f"{'PRODUTO (Original)':<35} | {'CATEGORIA (IA)':<20} | {'NOME LIMPO'}")
        print("="*85)

        cursor.execute("SELECT nome_original, categoria, nome_limpo FROM produtos")
        produtos = cursor.fetchall()

        for p in produtos:
            # Corta nomes muito longos para não quebrar a linha
            orig = (p[0][:32] + '..') if len(p[0]) > 32 else p[0]
            cat = (p[1][:18] + '..') if p[1] and len(p[1]) > 18 else (p[1] or "")
            limpo = p[2] or ""
            print(f"{orig:<35} | {cat:<20} | {limpo}")

        # 2. Relatório Financeiro
        print("\n" + "="*85)
        print("💰 ÚLTIMAS COMPRAS REGISTRADAS")
        print("="*85)
        
        cursor.execute("""
            SELECT h.data_compra, h.mercado, p.nome_limpo, h.preco_pago, h.quantidade 
            FROM historico_precos h
            JOIN produtos p ON h.ean = p.ean
            ORDER BY h.data_compra DESC
        """)
        
        historico = cursor.fetchall()
        for h in historico:
            data = str(h[0]) # Data
            mercado = (h[1][:20] + '..') if len(h[1]) > 20 else h[1]
            nome = (h[2][:20] + '..') if len(h[2]) > 20 else h[2]
            preco = h[3]
            print(f"{data} | {mercado:<22} | {nome:<22} | R$ {preco}")

        conn.close()

    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")

if __name__ == "__main__":
    mostrar_dados()