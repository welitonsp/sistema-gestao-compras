# simplificador_produtos.py
# Camada de regras para simplificar nomes de produtos brasileiros
# Ex.: "ARROZ PATOSUL 5KG TP1" -> produto="ARROZ", categoria="ALIMENTOS BÁSICOS"

from __future__ import annotations

import re
import unicodedata
from typing import Tuple


def _remover_acentos(texto: str) -> str:
    """Remove acentos de um texto e converte para ASCII básico."""
    if not isinstance(texto, str):
        texto = str(texto or "")
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in nfkd if not unicodedata.category(ch).startswith("M"))


class SimplificadorProdutos:
    """
    Classe simples para mapear descrições de cupom fiscal para:
      - produto_simplificado (ARROZ, FEIJÃO, SABONETE, etc.)
      - categoria (ALIMENTOS BÁSICOS, LATICÍNIOS, HIGIENE PESSOAL, etc.)

    Estratégia:
    1. Normaliza texto (maiúsculas, sem acento, sem pontuação estranha)
    2. Procura palavras-chave em uma tabela de regras
    3. Se não achar, tenta extrair primeira palavra "forte"
    4. Se ainda não achar, devolve trecho da descrição e categoria "OUTROS"
    """

    # Regras de mapeamento por palavra-chave.
    # Tudo deve estar SEM acento e em MAIÚSCULO para facilitar o matching.
    REGRAS = [
        # Alimentos básicos
        {"produto": "ARROZ", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["ARROZ"]},
        {"produto": "FEIJÃO", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["FEIJAO"]},
        {"produto": "AÇÚCAR", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["ACUCAR", "AÇUCAR", "ACUC"]},
        {"produto": "ÓLEO", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["OLEO", "ÓLEO"]},
        {"produto": "CAFÉ", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["CAFE", "CAFÉ"]},
        {"produto": "SAL", "categoria": "ALIMENTOS BÁSICOS", "keywords": [" SAL ", "SAL ", " SAL"]},
        {"produto": "MACARRÃO", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["MACARRAO", "MAC"]},
        {"produto": "FARINHA", "categoria": "ALIMENTOS BÁSICOS", "keywords": ["FARINHA"]},

        # Laticínios
        {"produto": "LEITE", "categoria": "LATICÍNIOS", "keywords": ["LEITE"]},
        {"produto": "QUEIJO", "categoria": "LATICÍNIOS", "keywords": ["QUEIJO", "QJO", "MUSS"]},
        {"produto": "IOGURTE", "categoria": "LATICÍNIOS", "keywords": ["IOGURTE", "IOG "]},
        {"produto": "MANTEIGA", "categoria": "LATICÍNIOS", "keywords": ["MANTEIGA"]},
        {"produto": "RICOTA", "categoria": "LATICÍNIOS", "keywords": ["RICOTA", "CR RICOTA"]},
        {"produto": "PETIT SUISSE", "categoria": "LATICÍNIOS", "keywords": ["PETIT", "SUISSE"]},

        # Carnes / Frios
        {"produto": "FRANGO", "categoria": "CARNES", "keywords": ["FRANGO", "SASSAMI", "COXA", "FILE", "FILÉ"]},
        {"produto": "LINGUIÇA", "categoria": "CARNES", "keywords": ["LING", "LINGUICA", "LINGUIÇA"]},
        {"produto": "CARNE", "categoria": "CARNES", "keywords": ["CARNE"]},
        {"produto": "SARDINHA", "categoria": "CARNES", "keywords": ["SARDINHA"]},
        {"produto": "BACON", "categoria": "CARNES", "keywords": ["BACON"]},
        {"produto": "PRESUNTO", "categoria": "CARNES", "keywords": ["PRESUNTO"]},
        {"produto": "MORTADELA", "categoria": "CARNES", "keywords": ["MORTADELA"]},

        # Hortifruti
        {"produto": "BANANA", "categoria": "HORTIFRUTI", "keywords": ["BANANA"]},
        {"produto": "BATATA", "categoria": "HORTIFRUTI", "keywords": ["BATATA"]},
        {"produto": "TOMATE", "categoria": "HORTIFRUTI", "keywords": ["TOMATE"]},
        {"produto": "CEBOLA", "categoria": "HORTIFRUTI", "keywords": ["CEBOLA"]},
        {"produto": "ALHO", "categoria": "HORTIFRUTI", "keywords": ["ALHO"]},
        {"produto": "LARANJA", "categoria": "HORTIFRUTI", "keywords": ["LARANJA"]},

        # Bebidas
        {"produto": "SUCO", "categoria": "BEBIDAS", "keywords": ["SUCO"]},
        {"produto": "REFRIGERANTE EM PÓ", "categoria": "BEBIDAS", "keywords": ["REFR PO", "REFR PÓ", "REFR PO ", "REFR PO."]},
        {"produto": "REFRIGERANTE", "categoria": "BEBIDAS", "keywords": ["REFRIG", "REFRIGERANTE"]},
        {"produto": "ÁGUA", "categoria": "BEBIDAS", "keywords": ["AGUA MINERAL", "ÁGUA MINERAL"]},
        {"produto": "CERVEJA", "categoria": "BEBIDAS", "keywords": ["CERVEJA"]},

        # Limpeza
        {"produto": "DETERGENTE", "categoria": "LIMPEZA", "keywords": ["DETERGENTE"]},
        {"produto": "LAVA ROUPAS", "categoria": "LIMPEZA", "keywords": ["LAVA ROUPAS", "LAVA ROUPA", "LAVA ROUP", "OMO ", "BRILHANTE"]},
        {"produto": "AMACIANTE", "categoria": "LIMPEZA", "keywords": ["AMAC", "AMACIANTE"]},
        {"produto": "DESINFETANTE", "categoria": "LIMPEZA", "keywords": ["DESINFETANTE"]},
        {"produto": "LIMPA MULTIUSO", "categoria": "LIMPEZA", "keywords": ["LIMP LIMPEZA", "LIMP PERF", "LIMP "]},
        {"produto": "SODA CÁUSTICA", "categoria": "LIMPEZA", "keywords": ["SODA CAUSTICA", "SODA CÁUSTICA"]},
        {"produto": "TIRA MANCHAS", "categoria": "LIMPEZA", "keywords": ["VANISH", "TIRA MANCHAS"]},
        {"produto": "PASTILHA SANITÁRIA", "categoria": "LIMPEZA", "keywords": ["PASTILHA SANIT"]},

        # Higiene pessoal
        {"produto": "SABONETE", "categoria": "HIGIENE PESSOAL", "keywords": ["SABONETE", "SAB "]},
        {"produto": "DESODORANTE", "categoria": "HIGIENE PESSOAL", "keywords": ["DEO AERO", "DEO ", "DESODORANTE"]},
        {"produto": "CREME DENTAL", "categoria": "HIGIENE PESSOAL", "keywords": ["CR DENT", "CREME DENTAL"]},
        {"produto": "ENXAGUANTE BUCAL", "categoria": "HIGIENE PESSOAL", "keywords": ["ENX BUCAL", "ENXAGUANTE"]},
        {"produto": "SHAMPOO", "categoria": "HIGIENE PESSOAL", "keywords": ["SH ", "SHAMPOO"]},
        {"produto": "ESPUMA DE BARBEAR", "categoria": "HIGIENE PESSOAL", "keywords": ["ESPUMA BARB"]},
        {"produto": "LENÇO UMEDECIDO", "categoria": "HIGIENE PESSOAL", "keywords": ["LENCO UMED", "LENÇO UMED"]},

        # Utilidades / Casa
        {"produto": "GARRAFA / FRASCO", "categoria": "UTENSÍLIOS", "keywords": ["FRASCO"]},
        {"produto": "GARFO", "categoria": "UTENSÍLIOS", "keywords": ["GARFO"]},
        {"produto": "TÁBUA", "categoria": "UTENSÍLIOS", "keywords": ["TABUA", "TÁBUA"]},
        {"produto": "PRENDEDOR DE CABELO", "categoria": "UTENSÍLIOS", "keywords": ["PRENDEDOR CAB"]},
        {"produto": "SANDÁLIA", "categoria": "VESTUÁRIO", "keywords": ["SAND HAVAIANAS", "SANDALIA", "SANDÁLIA"]},
    ]

    PALAVRAS_DESCARTAR = {
        "DE", "DA", "DO", "PARA", "COM", "SEM", "KG", "G", "ML", "L", "UN", "PCT", "CX",
        "UND", "UNID", "TPO", "TP1", "TP2", "TP", "SCH", "PT", "PVC"
    }

    def normalizar(self, descricao: str) -> str:
        """
        Normaliza texto:
          - remove acentos
          - deixa maiúsculo
          - troca pontuação estranha por espaço
          - remove espaços duplicados
        """
        texto = _remover_acentos(descricao).upper()
        texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()

    def simplificar(self, descricao: str) -> Tuple[str, str]:
        """
        Recebe uma descrição completa e devolve:
          (produto_simplificado, categoria)

        Se não encontrar nada, devolve:
          (TRECHO_DA_DESCRICAO, "OUTROS")
        """
        if not descricao:
            return "", "OUTROS"

        texto_norm = self.normalizar(descricao)

        # 1) Procura nas regras de palavra-chave
        for regra in self.REGRAS:
            for kw in regra["keywords"]:
                kw_norm = self.normalizar(kw)
                if kw_norm and kw_norm in texto_norm:
                    return regra["produto"], regra["categoria"]

        # 2) Se não encontrou, tenta usar a primeira palavra forte
        tokens = texto_norm.split()
        for tok in tokens:
            if tok in self.PALAVRAS_DESCARTAR:
                continue
            if len(tok) <= 2:
                continue
            # Primeira palavra "relevante"
            return tok, "OUTROS"

        # 3) Fallback absoluto: devolve início da descrição em maiúsculo
        return texto_norm[:20].strip(), "OUTROS"
