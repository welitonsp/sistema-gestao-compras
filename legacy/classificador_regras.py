# classificador_regras.py
import re
from typing import Tuple


def _normalizar(texto: str) -> str:
    """Normaliza texto para comparação (maiúsculas e espaços simples)."""
    texto = (texto or "").upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def aplicar_regras_nome_categoria(
    nome_original: str,
    nome_ia: str,
    categoria_ia: str,
) -> Tuple[str, str]:
    """
    Aplica regras determinísticas para:

      - Simplificar o nome do produto (ex: 'ARROZ TIPO 1 5KG' -> 'ARROZ')
      - Enquadrar a categoria em grupos fixos:
        'ALIMENTOS BÁSICOS', 'LATICÍNIOS', 'HORTIFRUTI',
        'BEBIDAS', 'LIMPEZA', 'HIGIENE PESSOAL',
        'LANCHE', 'OUTROS'

    Se nenhuma regra bater, mantém o que veio da IA (com alguns ajustes).
    """
    base = f"{nome_original} {nome_ia}"
    texto = f" {_normalizar(base)} "  # espaços nas pontas para facilitar buscas com ' in '

    # ---- 1. Regras específicas (ordem importa) -------------------------

    # SAL vs SALGADINHO
    if re.search(r"\bSALG(ADINHO)?\b", texto):
        return "SALGADINHO", "LANCHE"
    if re.search(r"\bSAL\b", texto):
        return "SAL", "ALIMENTOS BÁSICOS"

    # ARROZ
    if " ARROZ " in texto:
        return "ARROZ", "ALIMENTOS BÁSICOS"

    # FEIJÃO
    if " FEIJAO " in texto or " FEIJÃO " in texto:
        return "FEIJÃO", "ALIMENTOS BÁSICOS"

    # AÇÚCAR
    if " ACUCAR " in texto or " AÇÚCAR " in texto:
        return "AÇÚCAR", "ALIMENTOS BÁSICOS"

    # CAFÉ
    if " CAFE " in texto or " CAFÉ " in texto:
        return "CAFÉ", "ALIMENTOS BÁSICOS"

    # ÓLEOS (óleo + azeite vão para o mesmo grupo)
    if " OLEO " in texto or " ÓLEO " in texto or " AZEITE " in texto:
        return "ÓLEO / AZEITE", "ALIMENTOS BÁSICOS"

    # BANANA, BATATA, ALHO etc. -> HORTIFRUTI
    horti_keywords = [
        " BANANA ",
        " BATATA ",
        " TOMATE ",
        " CEBOLA ",
        " ALHO ",
        " ALFACE ",
        " MAÇA ",
        " MAÇÃ ",
        " LARANJA ",
        " LIMAO ",
        " LIMÃO ",
        " CENOURA ",
        " PIMENTAO ",
        " PIMENTÃO ",
    ]
    if any(k in texto for k in horti_keywords):
        # Mantém nome IA se vier algo melhor (ex: BANANA PRATA), senão usa primeira palavra forte
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            # fallback simples: primeira palavra relevante
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "HORTIFRUTI"
        return nome, "HORTIFRUTI"

    # LATICÍNIOS: LEITE, QUEIJO, IOGURTE, PETIT, RICOTA, MANTEIGA, REQUEIJÃO etc.
    laticinios_keywords = [
        " LEITE ",
        " QUEIJO ",
        " QJO ",
        " MUSS ",
        " MUSSARELA ",
        " RICOTA ",
        " IOG ",
        " IOGURTE ",
        " PETIT ",
        " REQUEIJAO ",
        " REQUEIJÃO ",
        " MANTEIGA ",
        " CREME DE LEITE ",
        " MARGARINA ",
    ]
    if any(k in texto for k in laticinios_keywords):
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "LATICÍNIOS"
        return nome, "LATICÍNIOS"

    # LIMPEZA
    limpeza_kw = [
        " LAVA ROUPAS ",
        " LAVA ROUPA ",
        " LAVA ",
        " DETERGENTE ",
        " DESINFETANTE ",
        " LIMP ",
        " VEJA ",
        " VANISH ",
        " SODA ",
        " DESENGORD ",
        " CIF ",
        " AJAX ",
        " AMAC ",
        " AMACIANTE ",
    ]
    if any(k in texto for k in limpeza_kw):
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "LIMPEZA"
        return nome, "LIMPEZA"

    # HIGIENE PESSOAL
    higiene_kw = [
        " SABONETE ",
        " SAB ",
        " SH ",
        " SHAMPOO ",
        " DESODORANTE ",
        " DEO ",
        " ENX ",
        " ENXAGUANTE ",
        " PASTA ",
        " DENTAL ",
        " ESCOVA DE DENTE ",
        " FRALDA ",
        " ABSORVENTE ",
        " COTONETE ",
        " HIGIENE ",
    ]
    if any(k in texto for k in higiene_kw):
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "HIGIENE"
        return nome, "HIGIENE PESSOAL"

    # LANCHE / BISCOITO / SALGADINHO / BOMBOM
    lanche_kw = [
        " BISCOITO ",
        " BISC ",
        " BOLACHA ",
        " BOLINHO ",
        " SALGAD ",
        " SALG ",
        " PIT STOP ",
        " TORTUGUITA ",
        " OREO ",
        " BOMBOM ",
        " CHOCOLATE ",
        " ROSQUINHA ",
        " SALG SKINY ",
        " ANELITOS ",
        " SALG KARITOS ",
    ]
    if any(k in texto for k in lanche_kw):
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "LANCHE"
        return nome, "LANCHE"

    # BEBIDAS
    bebidas_kw = [
        " REFRIGERANTE ",
        " REFR ",
        " REFRI ",
        " SUCO ",
        " SODA ",
        " AGUA ",
        " ÁGUA ",
        " CERVEJA ",
        " VINHO ",
        " ENERG ",
        " CHA ",
        " CHÁ ",
    ]
    if any(k in texto for k in bebidas_kw):
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "BEBIDA"
        return nome, "BEBIDAS"

    # Utensílios / outros itens de casa
    utensilios_kw = [
        " GARFO ",
        " FACA ",
        " COLHER ",
        " TABUA ",
        " TÁBUA ",
        " PANELA ",
        " FRIGIDEIRA ",
        " PRATO ",
        " COPO ",
        " PIREX ",
        " ASSADEIRA ",
        " PRENDEDOR ",
        " SANDALIA ",
        " SANDÁLIA ",
        " HAVAIANAS ",
        " LENCO UMED ",
        " LENÇO UMED ",
        " LENCOS UMED ",
        " LENÇOS UMED ",
    ]
    if any(k in texto for k in utensilios_kw):
        nome = nome_ia.strip().upper() if nome_ia else None
        if not nome:
            palavras = _normalizar(nome_original).split()
            nome = palavras[0] if palavras else "UTENSÍLIO"
        return nome, "OUTROS"

    # ---- 2. Se nenhuma regra específica bateu, trata retorno da IA --------

    produto_base = (nome_ia or nome_original or "PRODUTO").strip()
    produto_final = produto_base.upper()

    # Normaliza categoria em macrogrupos
    cat = (categoria_ia or "OUTROS").strip().upper()

    mapa_categorias = {
        "ALIMENTOS": "ALIMENTOS BÁSICOS",
        "ALIMENTOS BÁSICOS": "ALIMENTOS BÁSICOS",
        "ALIMENTOS CONFEITOS": "LANCHE",
        "CONFEITARIA": "LANCHE",
        "LATICINIOS": "LATICÍNIOS",
        "LATICÍNIOS": "LATICÍNIOS",
        "FRUTAS": "HORTIFRUTI",
        "HORTIFRUTIGRANJEIROS": "HORTIFRUTI",
        "HORTIFRUTI": "HORTIFRUTI",
        "BEBIDAS": "BEBIDAS",
        "LIMPEZA": "LIMPEZA",
        "HIGIENE": "HIGIENE PESSOAL",
        "HIGIENE PESSOAL": "HIGIENE PESSOAL",
        "UTENSÍLIOS": "OUTROS",
        "UTENSILIOS": "OUTROS",
        "ARTIGOS DE CALÇADO": "OUTROS",
        "OUTROS": "OUTROS",
    }

    categoria_final = mapa_categorias.get(cat, "OUTROS")

    return produto_final, categoria_final
