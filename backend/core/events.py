"""Simple internal event dispatcher."""

from __future__ import annotations
import asyncio
from typing import Any, Callable, Dict, List
from core.logger import get_logger

logger = get_logger("core.events")

class EventDispatcher:
    """Synchronous-like interface for asynchronous event handling."""
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, listener: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    async def publish(self, event_type: str, **kwargs):
        if event_type not in self._listeners:
            return
        
        logger.debug(f"Publishing event {event_type} with data {kwargs.keys()}")
        tasks = []
        for listener in self._listeners[event_type]:
            if asyncio.iscoroutinefunction(listener):
                tasks.append(listener(**kwargs))
            else:
                listener(**kwargs)
        
        if tasks:
            # We don't wait for all if we want truly background, 
            # but usually we want to ensure they start.
            asyncio.gather(*tasks, return_exceptions=True)

dispatcher = EventDispatcher()

# Event Constants
EVENT_NOTA_IMPORTADA = "nota.importada"
