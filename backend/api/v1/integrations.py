"""Routes for external integrations and open data."""

from __future__ import annotations
from typing import Any, List, Dict
import secrets
import hashlib
from fastapi import APIRouter, HTTPException, status, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import select
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.models.compras import APIKey, UserRole
from backend.services.erp_integration import ERPIntegrationService

router = APIRouter(prefix="/integrations", tags=["Integrações ERP & Open API"])

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def validate_api_key(
    db: DbSession,
    api_key: str = Security(api_key_header)
) -> APIKey:
    """Valida uma chave de API externa."""
    if not api_key:
        raise HTTPException(status_code=403, detail="Chave de API ausente.")
    
    # Busca por prefixo para otimizar e depois valida hash
    prefix = api_key[:8]
    stmt = select(APIKey).where(APIKey.key_prefix == prefix, APIKey.is_active == True)
    result = await db.execute(stmt)
    keys = result.scalars().all()
    
    for key in keys:
        if secrets.compare_digest(key.hashed_key, hashlib.sha256(api_key.encode()).hexdigest()):
            return key
            
    raise HTTPException(status_code=403, detail="Chave de API inválida.")

@router.post("/keys", summary="Gerar nova chave de API", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def gerar_api_key(name: str, department_id: str | None, db: DbSession):
    """Gera uma chave secreta para integração externa."""
    raw_key = f"sk_{secrets.token_urlsafe(32)}"
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    
    new_key = APIKey(
        name=name,
        department_id=department_id,
        key_prefix=raw_key[:8],
        hashed_key=hashed,
        is_active=True
    )
    db.add(new_key)
    await db.commit()
    
    return {"name": name, "api_key": raw_key, "warning": "Guarde esta chave, ela não será exibida novamente."}

@router.get("/erp/accounting", summary="Exportação Contábil (JSON)")
async def export_accounting(db: DbSession, api_key: APIKey = Depends(validate_api_key)):
    """Endpoint para ERPs buscarem dados de compras liquidadas."""
    service = ERPIntegrationService(db)
    return await service.get_accounting_payload(department_id=api_key.department_id)

@router.get("/open/prices", summary="Índice Público de Preços")
async def public_prices(db: DbSession, search: str | None = None):
    """Endpoint aberto para consulta de preços médios de mercado (Sem API Key necessária)."""
    service = ERPIntegrationService(db)
    return await service.get_price_index(search=search)
