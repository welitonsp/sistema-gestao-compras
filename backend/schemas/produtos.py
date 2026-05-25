from __future__ import annotations
from pydantic import BaseModel, ConfigDict

class ProdutoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome_limpo: str | None = None
    marca: str | None = None
    categoria: str | None = None
    unidade: str | None = None

class ProdutoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ean: str
    nome_limpo: str
    marca: str | None
    categoria: str
    unidade: str
