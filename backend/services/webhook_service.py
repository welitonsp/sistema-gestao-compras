import hmac
import hashlib
import json
import httpx
import asyncio
from typing import Any, Dict
from sqlalchemy import select
from backend.core.database import SessionLocal
from backend.models.compras import Webhook
from core.logger import get_logger

logger = get_logger("services.webhooks")

class WebhookService:
    """Service to manage and trigger external webhooks."""

    async def trigger_event(self, event_type: str, department_id: Any, payload: Dict[str, Any]):
        """
        Triggers a webhook for a specific event and department.
        Runs asynchronously to avoid blocking the main flow.
        """
        async with SessionLocal() as db:
            # Busca webhooks ativos inscritos para este evento e departamento (ou globais)
            stmt = select(Webhook).where(
                Webhook.is_active == True,
                Webhook.events.contains(event_type)
            )
            
            if department_id:
                stmt = stmt.where((Webhook.department_id == department_id) | (Webhook.department_id == None))
            else:
                stmt = stmt.where(Webhook.department_id == None)

            result = await db.execute(stmt)
            webhooks = result.scalars().all()

            if not webhooks:
                return

            # Dispara cada webhook em background
            tasks = [self._send_payload(wh, event_type, payload) for wh in webhooks]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_payload(self, webhook: Webhook, event_type: str, payload: Dict[str, Any]):
        """Sends the JSON payload to the target URL with a HMAC signature."""
        
        full_payload = {
            "event": event_type,
            "data": payload,
            "webhook_id": str(webhook.id)
        }
        
        body = json.dumps(full_payload)
        headers = {"Content-Type": "application/json"}
        
        if webhook.secret:
            signature = hmac.new(
                webhook.secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Hub-Signature-256"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook.url, content=body, headers=headers)
                resp.raise_for_status()
                logger.info(f"Webhook '{webhook.name}' enviado com sucesso para {event_type}")
        except Exception as e:
            logger.error(f"Falha ao enviar webhook '{webhook.name}': {e}")

# Singleton instance
webhook_service = WebhookService()
