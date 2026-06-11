from __future__ import annotations
import re
from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AgentIntent(str, Enum):
    PRICE_ANALYSIS = "PRICE_ANALYSIS"
    SPENDING_SUMMARY = "SPENDING_SUMMARY"
    ANOMALY_DETECTION = "ANOMALY_DETECTION"
    SAVINGS_FORECAST = "SAVINGS_FORECAST"
    CATALOG_HEALTH = "CATALOG_HEALTH"
    UNSUPPORTED = "UNSUPPORTED"


class AgentStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    PARTIAL_ERROR = "partial_error"
    INSUFFICIENT_DATA = "insufficient_data"


class AgentRecommendationType(str, Enum):
    SAVINGS_OPPORTUNITY = "savings_opportunity"
    PRICE_ALERT = "price_alert"
    CATALOG_SUGGESTION = "catalog_suggestion"
    ANOMALY_WARNING = "anomaly_warning"


class AgentQueryContext(BaseModel):
    current_page: Optional[str] = Field(None, max_length=100)
    active_filters: Optional[Dict[str, Union[str, int, float, bool, None]]] = None
    stream: bool = False

    model_config = ConfigDict(extra="forbid")


class AgentQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    context: Optional[AgentQueryContext] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be empty or just whitespace")
        return v


class AgentRecommendation(BaseModel):
    type: AgentRecommendationType
    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    impact_value_cents: Optional[int] = Field(None, ge=0)
    impact_label: Optional[str] = Field(None, max_length=50)
    action_link: Optional[str] = Field(None, max_length=255)

    model_config = ConfigDict(extra="forbid")


class AgentResponseMetadata(BaseModel):
    row_count: Optional[int] = None
    execution_time_ms: Optional[float] = None

    model_config = ConfigDict(extra="forbid")


class AgentQueryResponse(BaseModel):
    answer: str
    intent: AgentIntent
    status: AgentStatus
    metadata: AgentResponseMetadata
    recommendations: List[AgentRecommendation] = Field(default_factory=list)
    safe_id: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class AgentAuditMetadata(BaseModel):
    """Internal metadata for AuditLog details, contains sensitive debug info like query_hash."""
    origem: str = "purchasing_agent"
    action: str = "agent_query"
    intent: AgentIntent
    status: AgentStatus
    department_id: Optional[str] = None
    row_count: Optional[int] = None
    query_hash: Optional[str] = None
    reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("query_hash")
    @classmethod
    def validate_query_hash(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) != 64:
            raise ValueError("query_hash must be exactly 64 characters long")
        if not re.fullmatch(r"[0-9a-fA-F]+", v):
            raise ValueError("query_hash must contain only hexadecimal characters")
        return v.lower()
