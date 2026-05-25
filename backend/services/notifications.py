import asyncio
from typing import AsyncGenerator, Dict, List
import json
from core.logger import get_logger

logger = get_logger("services.notifications")

class NotificationDispatcher:
    """
    Dispatcher centralizado para Server-Sent Events (SSE).
    Permite que diferentes partes do sistema enviem notificações para o frontend em tempo real.
    """
    def __init__(self):
        self.queues: List[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Inscreve um cliente para receber o stream de eventos."""
        queue = asyncio.Queue()
        self.queues.append(queue)
        logger.info(f"Novo cliente inscrito no stream de eventos (Total: {len(self.queues)})")
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            self.queues.remove(queue)
            logger.info(f"Cliente desconectado (Total: {len(self.queues)})")

    async def broadcast(self, event_type: str, payload: Dict):
        """Envia uma mensagem para todos os clientes conectados."""
        if not self.queues:
            return

        message = {
            "type": event_type,
            "payload": payload,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Envia para todas as filas ativas
        for queue in self.queues:
            await queue.put(message)

# Instância global para ser usada em todo o backend
dispatcher = NotificationDispatcher()
