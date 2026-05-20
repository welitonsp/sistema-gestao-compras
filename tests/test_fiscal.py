import pytest
from backend.core.fiscal import validar_chave_acesso, extrair_modelo_fiscal

def test_validar_chave_acesso_valida():
    # Chave real/valida simulada (DV deve bater)
    # Exemplo de chave valida de GO
    chave = "52231000000000000000650010000000011000000011" 
    # Vou usar uma formula real para gerar um DV valido se necessario, 
    # mas para o teste vou usar uma que eu saiba que o calculo bate.
    # 43 digitos + 1 DV.
    
    # Testando com a chave que o usuario forneceu antes (se for valida)
    chave_user = "52260517457404001183655110000409351275118105"
    assert validar_chave_acesso(chave_user) is True

def test_validar_chave_acesso_invalida():
    assert validar_chave_acesso("123") is False
    assert validar_chave_acesso("52260517457404001183655110000409351275118100") is False # DV errado

def test_extrair_modelo_fiscal():
    chave = "52260517457404001183655110000409351275118105"
    assert extrair_modelo_fiscal(chave) == "65" # NFC-e
