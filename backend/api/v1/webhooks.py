"""Routes for webhook management."""

from __future__ import annotations

from typing import List
import json
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from backend.api.dependencies import DbSession, CurrentUser, RoleChecker
from backend.models.compras import Webhook, UserRole
from backend.schemas.webhooks import WebhookResponse, WebhookCreate

router = APIRouter(prefix="/webhooks", tags=["Configurações & Webhooks"])

@router.get(
    "",
    response_model=List[WebhookResponse],
    summary="Listar webhooks configurados",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def listar_webhooks(db: DbSession, user: CurrentUser):
    """Retorna a lista de webhooks ativos e inativos."""
    stmt = select(Webhook).order_by(Webhook.name)
    result = await db.execute(stmt)
    webhooks = result.scalars().all()
    
    # Converte string JSON para lista para o schema
    for wh in webhooks:
        wh.events = json.loads(wh.events)
        
    return webhooks

@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo webhook",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def criar_webhook(payload: WebhookCreate, db: DbSession):
    """Registra um novo endpoint para notificações automatizadas."""
    webhook = Webhook(
        name=payload.name,
        url=str(payload.url),
        events=json.dumps(payload.events),
        secret=payload.secret,
        department_id=payload.department_id,
        is_active=payload.is_active
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    
    webhook.events = json.loads(webhook.events) # Re-converte para o schema
    return webhook

@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover webhook",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def remover_webhook(webhook_id: str, db: DbSession):
    """Remove permanentemente um webhook."""
    stmt = select(Webhook).where(Webhook.id == webhook_id)
    webhook = (await db.execute(stmt)).scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook não encontrado.")
    
    await db.delete(webhook)
    await db.commit()
    return None
