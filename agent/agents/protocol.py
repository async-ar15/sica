from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    """Which sub-agent generated this message."""
    ORCHESTRATOR = "orchestrator"
    ARCHITECT = "architect"
    WORKER = "worker"
    JUDGE = "judge"

class MessageType(StrEnum):
    """Type of inter-agent message."""
    PLAN = "plan"
    CODE = "code"
    REVIEW = "review"
    REFLECTION = "reflection"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

class AgentMessage(BaseModel):
    """Typed message between agents or between harness and agent."""
    from_agent: AgentRole
    to_agent: AgentRole
    message_type: MessageType
    content: str
    confidence: float = 1.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
