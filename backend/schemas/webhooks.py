from __future__ import annotations
from pydantic import BaseModel, HttpUrl, ConfigDict
from uuid import UUID
from typing import List

class WebhookBase(BaseModel):
    name: str
    url: HttpUrl
    events: List[str]
    is_active: bool = True
    department_id: UUID | None = None

class WebhookCreate(WebhookBase):
    secret: str | None = None

class WebhookResponse(WebhookBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    url: str # HttpUrl serialize as string
