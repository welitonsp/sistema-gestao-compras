"""Fiscal domain logic and validations."""

from __future__ import annotations

import re

def validar_chave_acesso(chave: str) -> bool:
    """
    Valida uma chave de acesso de documento fiscal (NF-e/NFC-e) usando o dígito verificador.
    
    A chave deve ter 44 dígitos numéricos.
    """
    chave = re.sub(r"\D", "", chave)
    
    if len(chave) != 44:
        return False
        
    # Cálculo do Dígito Verificador (Módulo 11)
    # Pesos: 2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4... (da direita para a esquerda)
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    
    # Inverte a chave excluindo o último dígito (o próprio DV)
    chave_base = chave[:-1][::-1]
    
    for i, digito in enumerate(chave_base):
        peso = pesos[i % len(pesos)]
        soma += int(digito) * peso
        
    resto = soma % 11
    dv_calculado = 0 if resto in (0, 1) else 11 - resto
    
    return dv_calculado == int(chave[-1])


def extrair_modelo_fiscal(chave: str) -> str | None:
    """Retorna o modelo do documento (55 para NF-e, 65 para NFC-e)."""
    if len(chave) == 44:
        return chave[20:22]
    return None
