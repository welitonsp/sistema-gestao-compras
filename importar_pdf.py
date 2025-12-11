import os
from datetime import datetime

from ia_groq_utils import (
    criar_tabelas_se_nao_existirem,
    produto_ja_existe,
    salvar_produto,
    salvar_compra,
    classificar_produto,
)

# ==========================================
# 1. EXTRAÇÃO DO PDF (SIMULADA)
# ==========================================

def extrair_dados_pdf(caminho_arquivo: str):
    """
    Simula a extração de dados de um PDF de nota fiscal.
    Em produção, esta função será substituída por um extrator real (PDF/OCR).
    Por enquanto, usamos os dados da nota de exemplo.
    """
    print(f"📄 (SIMULAÇÃO) Lendo dados do PDF: {caminho_arquivo}")

    # Data e mercado do exemplo
    data_compra = "2025-06-16"
    nome_mercado = "ATACADAO DIA A DIA S.A"

    # Lista de itens da nota fiscal (exemplo real que você forneceu)
    itens = [
        ("5428", "JARDINEIRA CONG DEMARCHI 1.02kg C MILHO", 1.000, 17.99),
        ("10456", "EMP PERDIGAO BIG CHICKEN 1kg TRAD", 1.000, 26.99),
        ("4704", "FILEZINHO SASSAMI SUPER FRANGO IQF FGO", 1.000, 21.99),
        ("1821", "PETIT SUISSE TREVINHO LANCHE 70G MOR", 4.000, 1.99),
        ("15416", "LING FRANGO LAR FININHA CONG PCT 1K NG PCT 1", 1.000, 16.49),
        ("2327", "QJO MUSS DEALE 400G FAT", 1.000, 15.99),
        ("10368", "PATE SADIA 100G PEITO PERU", 1.000, 4.39),
        ("2327", "QJO MUSS DEALE 400G FAT", 1.000, 15.99),
        ("15685", "IOG LIQ TREVINHO 1.100kg MOR", 1.000, 7.99),
        ("5284", "IOG FRUTAP 850G ACAI BAN", 1.000, 8.79),
        ("16089", "CR RICOTA LIGHT TIROLEZ 370G", 1.000, 12.49),
        ("5110", "GRANOLA NATUREZA E CIA 800G MIX", 1.000, 14.99),
        ("13495", "BOLINHO RECH BAUDUCCO 40G CHOC BAUN CHOC BAU", 16.000, 1.79),
        ("2952", "PAO FORMA SEVENBOYS 450G LEITE", 2.000, 8.99),
        ("2893", "PAO FORMA INTG DI NAPOLI 500G TRAD", 2.000, 7.79),
        ("20294", "ROSQUINHA ADORALLE 600G COCO", 1.000, 7.39),
        ("12446", "BISC RECH OREO 36G CHOC", 8.000, 2.29),
        ("11383", "BISC INTG CLUB SOCIAL 288G ORIG", 1.000, 8.99),
        ("8099", "BOMBOM CX LACTA 250.6G BRAND MIX", 1.000, 11.99),
        ("918", "ARROZ PATOSUL 5kg TP1", 1.000, 18.99),
        ("8101", "BOMBOM CX TORTUGUITA 134.5G", 1.000, 8.79),
        ("10511", "MOLHO TOM POMAROLA CASEIRO SCH 300G MANJERIC", 1.000, 4.39),
        ("10510", "MOLHO TOM POMAROLA CASEIRO SCH 300G CLASSIC", 1.000, 4.39),
        ("6211", "SALG ANELITOS 41G CEB", 2.000, 2.99),
        ("9008", "FEIJÃO DA MAMAE 1kg CARIOCA", 1.000, 4.99),
        ("9008", "FEIJÃO DA MAMAE 1kg CARIOCA", 1.000, 4.99),
        ("6235", "SALG KARITOS 40G BACON", 6.000, 1.99),
        ("12351", "CAFE PILAO POUCH 500G TRAD", 1.000, 27.99),
        ("13277", "BISC RECH CLUB SOCIAL 141G CEB SOUR", 1.000, 4.79),
        ("7928", "BISC MARILAN PIT STOP 137G PAO NA CHAPA", 1.000, 4.99),
        ("15577", "BATATA CRONY 35G CHURR 35G CHURR", 3.000, 2.79),
        ("16197", "SALG SKINY 60G ORIG", 2.000, 1.99),
        ("4171", "OVO STA CLARA PVC 30UN BCO", 1.000, 17.99),
        ("13277", "BISC RECH CLUB SOCIAL 141G CEB SOUR", 1.000, 4.79),
        ("13457", "GELATINA APTI 20G MARAC", 1.000, 1.39),
        ("6899", "TEMP TEMPERE 30G ANA MARIA", 1.000, 2.59),
        ("6898", "TEMP TEMPERE 30G ALHO CEB TOM", 1.000, 3.59),
        ("17992", "GELATINA DR OETKER SCH C 2 INCOLOR 2 INCOLO", 1.000, 6.79),
        ("6211", "SALG ANELITOS 41G CEB", 1.000, 2.99),
        ("13003", "GARFO MESA TRAMONTINA LEME VERM", 6.000, 1.99),
        ("3973", "MOSTARDA BONARE 190G AMARELA", 1.000, 6.99),
        ("13415", "REFR PO TANG 18G UVA", 4.000, 0.99),
        ("13414", "REFR PO TANG 18G MARAC", 6.000, 0.99),
        ("12694", "SARDINHA 88 MANJUBA BOCA TORTA 125G TOM", 3.000, 6.39),
        ("1052", "AZEITE PORT ANDORINHA 500ML TP UNICO PURO", 1.000, 34.90),
        ("12622", "OLEO SOJA VILA VELHA 900ML", 1.000, 6.49),
        ("3550", "MEL PIMEL 1kg", 1.000, 39.99),
        ("12467", "MAC INST CUP NOODLES 65G COSTELA CHURR", 1.000, 4.29),
        ("12466", "MAC INST CUP NOODLES 65G GALINHA PIC", 2.000, 4.29),
        ("12457", "MAC INST CUP NOODLES 65G GALINHA CAIP", 1.000, 4.29),
        ("21127", "EXT TOM ELEFANTE PT 300G CARNE PANELA", 1.000, 7.79),
        ("14146", "SUCO MISTO SUMMER VIBES 1L MARAC UVA BCA", 1.000, 9.99),
        ("14105", "SUCO MISTO SUMMER VIBES 1L ABAC MACA UVA", 1.000, 9.99),
        ("6121", "VINAGRE ALCOOL CASTELO 750ML LIMAO", 1.000, 6.79),
        ("4333", "LENCO UMED SELECT WIPES BABY 100UN", 1.000, 9.99),
        ("21723", "TABUA PLASTICO INGA ESTAMPADA", 1.000, 12.99),
        ("2131", "PRENDEDOR CAB BELLISSIMA 3UN MEDIO", 1.000, 5.79),
        ("14878", "SAND HAVAIANAS SLIM FEM 312 ROSA BALLET", 1.000, 28.99),
        ("11405", "SAB LIQ GRANADO BEBE REF 250ML ERVA DOCE", 1.000, 15.49),
        ("10639", "ESPUMA BARB GILLETTE 150G SENS", 1.000, 19.99),
        ("12963", "DEO AERO NIVEA MASC 200ML BLACK WHITE", 1.000, 17.49),
        ("10036", "ENX BUCAL ORAL B L500 P300 COMPL HORT", 1.000, 15.99),
        ("6512", "SH OX 400ML LISOS", 1.000, 23.99),
        ("11055", "DEO AERO NIVEA MASC 150ML SENS PROT", 1.000, 14.99),
        ("11528", "LIMP PERF VEJA 2L FLORES", 1.000, 9.99),
        ("5537", "PACK TIRA MANCHAS GEL VANISH 1.2L BCO ROSA", 1.000, 53.99),
        ("541", "BANANA PRATA kg", 2.410, 5.99),
        ("14322", "PASTILHA SANIT INSPIRA 3UN MARINE", 1.000, 5.79),
        ("15609", "CR DENT SORRISO XTREME 140G FRESH MINT", 1.000, 5.99),
        ("16214", "DIFUSOR COALA 100ML TANG PATCHOULI", 2.000, 11.99),
        ("14125", "SAB FRANCIS BRASILIDADES 80G LARANJA", 1.000, 2.79),
        ("5595", "LAVA ROUPAS LIQ OMO 3L PURO CUIDADO", 1.000, 39.99),
        ("5577", "LAVA ROUPAS LIQ BRILHANTE 3L LIMP TOTAL", 1.000, 39.99),
        ("11374", "LIMP LIMPEZA PESADA AJAX 1L LIMAO", 1.000, 17.49),
        ("13253", "AMAC YPE 2L DELICADO", 1.000, 11.49),
        ("6629", "SODA CAUSTICA SOL 1kg", 1.000, 21.99),
    ]

    print(f"✅ Dados simulados carregados: {len(itens)} itens.")
    return data_compra, nome_mercado, itens


# ==========================================
# 2. LÓGICA DE IMPORTAÇÃO
# ==========================================

def importar_pdf_direto(caminho_pdf: str):
    """
    Processa um PDF (ou melhor, os dados simulados dele) e salva tudo no banco.
    """
    print("\n" + "=" * 60)
    print(f"🚀 INICIANDO IMPORTAÇÃO DO ARQUIVO: {os.path.basename(caminho_pdf)}")
    print("=" * 60)

    # 1. Extrai os dados (simulados)
    data_compra, nome_mercado, itens = extrair_dados_pdf(caminho_pdf)

    if not itens:
        print("❌ Nenhum item encontrado na nota. Nada foi importado.")
        return

    print(f"\n🛒 Mercado: {nome_mercado}")
    print(f"📅 Data da compra: {data_compra}")
    print(f"📦 Total de itens na nota: {len(itens)}")
    print("-" * 50)

    itens_processados = 0
    itens_novos = 0

    for ean, nome_original, qtd, preco_unit in itens:
        ean_str = str(ean)

        try:
            # Verifica se o produto já existe
            if produto_ja_existe(ean_str):
                print(f"✅ Produto conhecido [{ean_str}]: {nome_original[:40]}{'...' if len(nome_original) > 40 else ''}")
                dados_ia = None
            else:
                print(f"🆕 Produto novo [{ean_str}]: {nome_original[:40]}{'...' if len(nome_original) > 40 else ''}")
                dados_ia = classificar_produto(nome_original)
                itens_novos += 1

                salvar_produto(
                    ean_str,
                    nome_original,
                    dados_ia["produto"],
                    dados_ia["marca"],
                    dados_ia["categoria"],
                    dados_ia["unidade"],
                )
                print(f"   💾 Produto salvo: {dados_ia['produto']} ({dados_ia['categoria']})")

            # Sempre registra a compra no histórico
            salvar_compra(
                ean_str,
                data_compra,
                nome_mercado,
                float(preco_unit),
                float(qtd),
            )
            itens_processados += 1

        except Exception as e:
            print(f"   ❌ Erro ao processar item [{ean_str}]: {str(e)[:120]}")
            continue

    print("-" * 50)
    print("✅ IMPORTAÇÃO CONCLUÍDA!")
    print(f"   Itens processados: {itens_processados}/{len(itens)}")
    print(f"   Novos produtos cadastrados: {itens_novos}")
    print(f"   Data/hora do processamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


# ==========================================
# 3. PONTO DE ENTRADA (EXECUÇÃO DIRETA)
# ==========================================

if __name__ == "__main__":
    print("\n📊 IMPORTADOR DE NOTA FISCAL (PDF) - MODO DEMONSTRATIVO\n")

    # Garante tabelas no banco
    criar_tabelas_se_nao_existirem()

    # Nome do arquivo de exemplo (pode ajustar)
    nome_arquivo_pdf = "b5c8f464-ba83-4a53-88d4-2667ea9896e9.pdf"

    if not os.path.exists(nome_arquivo_pdf):
        print(f"⚠️ ATENÇÃO: O arquivo '{nome_arquivo_pdf}' não foi encontrado na pasta atual.")
        print("   Mesmo assim, vamos importar usando os dados simulados da nota de exemplo.")
    else:
        print(f"✅ Arquivo '{nome_arquivo_pdf}' encontrado. Usando-o como referência.")

    importar_pdf_direto(nome_arquivo_pdf)
    print("\n✨ Fim do processo de importação demonstrativa.")
