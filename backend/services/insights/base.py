"""Base utilities for insights services."""

from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy import or_
from backend.models.compras import HistoricoPreco, NotaFiscal

ACTIVE_INVOICE_STATUS = "active"

def historico_visivel_filter():
    return or_(
        HistoricoPreco.nota_fiscal_id == None,
        NotaFiscal.status == ACTIVE_INVOICE_STATUS,
    )

def historico_department_filter(department_id: UUID | None):
    if department_id is None:
        return None
    return or_(
        HistoricoPreco.nota_fiscal_id == None, NotaFiscal.department_id == department_id
    )
