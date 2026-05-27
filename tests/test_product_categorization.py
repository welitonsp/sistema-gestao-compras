from __future__ import annotations

import pytest

from backend.services.product_categorization import (
    CATEGORIAS_CANONICAS,
    categorizar_produto,
    categorizar_produtos,
    normalizar_descricao_produto,
)


@pytest.mark.parametrize(
    ("descricao", "categoria", "subcategoria", "produto_base"),
    [
        ("ARROZ TIPO 1 C", "MERCEARIA", "ARROZ", "ARROZ"),
        ("ARROZ TIPO 1 D", "MERCEARIA", "ARROZ", "ARROZ"),
        ("QUEIJO MUSSARELA", "FRIOS E LATICÍNIOS", "QUEIJOS", "QUEIJO"),
        ("IOGURTE NATURAL", "FRIOS E LATICÍNIOS", "IOGURTES", "IOGURTE"),
        ("DESINFETANTE", "LIMPEZA", None, "LIMPEZA"),
        ("SHAMPOO", "HIGIENE E BELEZA", None, "HIGIENE"),
        ("MAC CRISTAL SEMOLA", "MERCEARIA", "MASSAS", "MASSA"),
        ("MASSA RAVIOLI", "MERCEARIA", "MASSAS", "MASSA"),
    ],
)
def test_categoriza_produtos_por_regras_deterministicas(descricao, categoria, subcategoria, produto_base):
    resultado = categorizar_produto(descricao)

    assert resultado.descricao_original == descricao
    assert resultado.categoria == categoria
    assert resultado.subcategoria == subcategoria
    assert resultado.produto_base == produto_base
    assert resultado.origem_categorizacao == "deterministica"
    assert resultado.confianca >= 0.9


def test_produto_desconhecido_retorna_outros_com_baixa_confianca():
    resultado = categorizar_produto("PRODUTO SINTETICO SEM REGRA")

    assert resultado.categoria == "OUTROS"
    assert resultado.subcategoria is None
    assert resultado.produto_base == "OUTROS"
    assert resultado.origem_categorizacao == "sem_regra"
    assert resultado.confianca < 0.5


def test_normalizacao_remove_acentos_caixa_e_espacos_sem_alterar_original():
    descricao = "  Feijão   Tipo 1  "
    resultado = categorizar_produto(descricao)

    assert normalizar_descricao_produto(descricao) == "feijao tipo 1"
    assert resultado.descricao_original == descricao
    assert resultado.descricao_normalizada == "feijao tipo 1"
    assert resultado.produto_base == "FEIJÃO"


def test_categorias_retornadas_pertencem_a_taxonomia_fechada():
    descricoes = [
        "ARROZ TIPO 1",
        "FEIJAO CARIOCA",
        "QUEIJO MUSSARELA",
        "IOGURTE NATURAL",
        "LEITE INTEGRAL",
        "MAC CRISTAL SEMOLA",
        "MASSA RAVIOLI",
        "VINAGRE",
        "AZEITE",
        "DESINFETANTE",
        "SHAMPOO",
        "RODO",
        "PRODUTO SINTETICO SEM REGRA",
    ]

    resultados = categorizar_produtos(descricoes)

    assert {resultado.categoria for resultado in resultados} <= set(CATEGORIAS_CANONICAS)
