import pytest
from backend.core.fiscal import validar_chave_acesso, extrair_modelo_fiscal

def test_validar_chave_acesso_valida():
    # Chave real baseada no cálculo de Módulo 11 (DV calculado como 6)
    chave_valida = "52260517457404001183655110000409351275118106"
    assert validar_chave_acesso(chave_valida) is True

def test_validar_chave_acesso_invalida():
    assert validar_chave_acesso("123") is False
    assert validar_chave_acesso("52260517457404001183655110000409351275118100") is False # DV errado

def test_extrair_modelo_fiscal():
    chave = "52260517457404001183655110000409351275118105"
    assert extrair_modelo_fiscal(chave) == "65" # NFC-e
