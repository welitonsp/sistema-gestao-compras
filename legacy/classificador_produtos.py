# classificador_produtos.py
# Classificador/simplificador local de produtos de supermercado
# Exemplo:
#   "ARROZ TIPO 1 B 5KG" -> ("ARROZ", "ALIMENTOS BÁSICOS")

import re
import unicodedata
from typing import Tuple


class SimplificadorProdutos:
    """
    Classificador simples baseado em regras.
    - Não usa IA
    - Focado em produtos comuns de supermercado brasileiro
    """

    def __init__(self) -> None:
        # (chave_normalizada, nome_simplificado_bonito, categoria)
        self._palavras_chave = [
            # Alimentos básicos
            ("ARROZ", "ARROZ", "ALIMENTOS BÁSICOS"),
            ("FEIJAO", "FEIJÃO", "ALIMENTOS BÁSICOS"),
            ("FEIJÃO", "FEIJÃO", "ALIMENTOS BÁSICOS"),
            ("AÇUCAR", "AÇÚCAR", "ALIMENTOS BÁSICOS"),
            ("ACUCAR", "AÇÚCAR", "ALIMENTOS BÁSICOS"),
            ("OLEO", "ÓLEO", "ALIMENTOS BÁSICOS"),
            ("ÓLEO", "ÓLEO", "ALIMENTOS BÁSICOS"),
            ("SAL ", "SAL", "ALIMENTOS BÁSICOS"),
            ("FARINHA", "FARINHA", "ALIMENTOS BÁSICOS"),
            ("MACARRAO", "MACARRÃO", "ALIMENTOS BÁSICOS"),
            ("MACARRÃO", "MACARRÃO", "ALIMENTOS BÁSICOS"),
            ("CAFÉ", "CAFÉ", "ALIMENTOS BÁSICOS"),
            ("CAFE", "CAFÉ", "ALIMENTOS BÁSICOS"),

            # Laticínios
            ("LEITE", "LEITE", "LATICÍNIOS"),
            ("QUEIJO", "QUEIJO", "LATICÍNIOS"),
            ("MANTEIGA", "MANTEIGA", "LATICÍNIOS"),
            ("IOGURTE", "IOGURTE", "LATICÍNIOS"),
            ("REQUEIJAO", "REQUEIJÃO", "LATICÍNIOS"),
            ("REQUEIJÃO", "REQUEIJÃO", "LATICÍNIOS"),

            # Carnes
            ("CARNE", "CARNE", "CARNES"),
            ("FRANGO", "FRANGO", "CARNES"),
            ("PEIXE", "PEIXE", "CARNES"),
            ("LINGUIÇA", "LINGUIÇA", "CARNES"),
            ("LINGUICA", "LINGUIÇA", "CARNES"),
            ("SALSICHA", "SALSICHA", "CARNES"),
            ("BACON", "BACON", "CARNES"),

            # Hortifruti
            ("BATATA", "BATATA", "HORTIFRUTI"),
            ("TOMATE", "TOMATE", "HORTIFRUTI"),
            ("CEBOLA", "CEBOLA", "HORTIFRUTI"),
            ("ALHO", "ALHO", "HORTIFRUTI"),
            ("ALFACE", "ALFACE", "HORTIFRUTI"),
            ("BANANA", "BANANA", "HORTIFRUTI"),
            ("MAÇA", "MAÇÃ", "HORTIFRUTI"),
            ("MACA", "MAÇÃ", "HORTIFRUTI"),
            ("LARANJA", "LARANJA", "HORTIFRUTI"),
            ("LIMAO", "LIMÃO", "HORTIFRUTI"),
            ("LIMÃO", "LIMÃO", "HORTIFRUTI"),

            # Limpeza
            ("DETERGENTE", "DETERGENTE", "LIMPEZA"),
            ("SABAO EM PO", "SABÃO EM PÓ", "LIMPEZA"),
            ("SABAO", "SABÃO", "LIMPEZA"),
            ("AMACIANTE", "AMACIANTE", "LIMPEZA"),
            ("DESINFETANTE", "DESINFETANTE", "LIMPEZA"),
            ("LIMPADOR", "LIMPADOR", "LIMPEZA"),

            # Higiene pessoal
            ("SABONETE", "SABONETE", "HIGIENE PESSOAL"),
            ("SHAMPOO", "SHAMPOO", "HIGIENE PESSOAL"),
            ("CONDICIONADOR", "CONDICIONADOR", "HIGIENE PESSOAL"),
            ("PAPEL HIGIENICO", "PAPEL HIGIÊNICO", "HIGIENE PESSOAL"),
            ("PAPEL HIGIÊNICO", "PAPEL HIGIÊNICO", "HIGIENE PESSOAL"),
            ("CREME DENTAL", "CREME DENTAL", "HIGIENE PESSOAL"),
            ("PASTA DE DENTE", "CREME DENTAL", "HIGIENE PESSOAL"),

            # Bebidas
            ("REFRIGERANTE", "REFRIGERANTE", "BEBIDAS"),
            ("CERVEJA", "CERVEJA", "BEBIDAS"),
            ("SUCO", "SUCO", "BEBIDAS"),
            ("AGUA", "ÁGUA", "BEBIDAS"),
            ("ÁGUA", "ÁGUA", "BEBIDAS"),
        ]

        # Palavras que vamos ignorar na hora de pegar "primeira palavra útil"
        self._stopwords = {
            "DE", "DA", "DO", "KG", "G", "GR", "L", "ML",
            "UN", "PCT", "PACOTE", "CX", "CAIXA"
        }

    @staticmethod
    def _remover_acentos(texto: str) -> str:
        texto_norm = unicodedata.normalize("NFD", texto)
        return "".join(ch for ch in texto_norm if unicodedata.category(ch) != "Mn")

    def normalizar_texto(self, texto: str) -> str:
        """
        Deixa o texto em maiúsculo, sem acentos e sem caracteres estranhos.
        """
        if not texto:
            return ""
        texto = texto.upper()
        texto = self._remover_acentos(texto)
        texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()

    def inferir_unidade(self, descricao: str) -> str:
        """
        Chute simples de unidade a partir do texto.
        Ex.: "5KG" -> "kg", "500ML" -> "ml"
        """
        if not descricao:
            return "un"

        desc = self.normalizar_texto(descricao)

        if "KG" in desc:
            return "kg"
        if " G " in f" {desc} " or desc.endswith("G"):
            return "g"
        if "ML" in desc:
            return "ml"
        if " L " in f" {desc} " or desc.endswith("L"):
            return "l"
        if "UN " in f" {desc} " or desc.endswith("UN"):
            return "un"
        if "PCT" in desc or "PACOTE" in desc:
            return "pct"

        return "un"

    def simplificar(self, descricao: str) -> Tuple[str, str]:
        """
        Simplifica uma descrição de produto.
        Exemplo: "ARROZ TIPO 1 B 5KG" -> ("ARROZ", "ALIMENTOS BÁSICOS")
        """
        if not descricao:
            return "", "OUTROS"

        desc_norm = self.normalizar_texto(descricao)

        # 1) Tentar bater com a lista de palavras-chave
        for chave, nome_simplificado, categoria in self._palavras_chave:
            chave_norm = self.normalizar_texto(chave)
            if chave_norm and chave_norm in desc_norm:
                return nome_simplificado, categoria

        # 2) Se não achou, pegar primeira palavra "útil"
        palavras = desc_norm.split()
        for p in palavras:
            if p not in self._stopwords and len(p) > 2:
                # Ex.: "BATATA" -> categoria Hortifruti, "ARROZ" -> Alimentos etc.
                categoria = self._inferir_categoria_por_palavra(p)
                return p, categoria

        # 3) Fallback bruto
        return desc_norm, "OUTROS"

    def _inferir_categoria_por_palavra(self, palavra: str) -> str:
        """
        Tenta inferir categoria só pela primeira palavra detectada.
        """
        p = palavra.upper()

        # Mapas simples
        if p in {"ARROZ", "FEIJAO", "FEIJÃO", "ACUCAR", "AÇUCAR", "OLEO", "ÓLEO"}:
            return "ALIMENTOS BÁSICOS"
        if p in {"LEITE", "QUEIJO", "MANTEIGA", "IOGURTE", "REQUEIJAO", "REQUEIJÃO"}:
            return "LATICÍNIOS"
        if p in {"CARNE", "FRANGO", "PEIXE", "LINGUIÇA", "LINGUICA", "SALSICHA"}:
            return "CARNES"
        if p in {"BATATA", "TOMATE", "CEBOLA", "ALHO", "BANANA", "MACA", "MAÇA", "LARANJA"}:
            return "HORTIFRUTI"
        if p in {"DETERGENTE", "SABAO", "AMACIANTE", "DESINFETANTE"}:
            return "LIMPEZA"
        if p in {"SABONETE", "SHAMPOO", "CONDICIONADOR"}:
            return "HIGIENE PESSOAL"
        if p in {"REFRIGERANTE", "CERVEJA", "SUCO", "AGUA"}:
            return "BEBIDAS"

        return "OUTROS"


if __name__ == "__main__":
    # Teste rápido
    s = SimplificadorProdutos()
    testes = [
        "ARROZ TIPO 1 B 5KG",
        "FEIJÃO CARIOCA 1KG",
        "AÇÚCAR CRISTAL ESPECIAL 1KG",
        "LEITE INTEGRAL 1L",
        "DETERGENTE LÍQUIDO YPÊ 500ML",
        "SABONETE DOVE 90G",
        "BANANA PRATA KG",
        "BATATA LAVADA 2KG",
    ]
    for t in testes:
        prod, cat = s.simplificar(t)
        uni = s.inferir_unidade(t)
        print(f"{t} -> {prod} | {cat} | unidade: {uni}")
