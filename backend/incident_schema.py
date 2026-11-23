"""Record replay checks for the actual cue IDs affected by an on-air incident."""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Cause(StrEnum):
    MONITORING = "monitoring"
    LATENCY_QUEUE = "latency_queue"
    MISSING_CONTEXT = "missing_context"
    HANDOFF = "handoff"


class IncidentDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    track_version: int = Field(gt=0)
    cause: Cause
    countermeasure: str = Field(min_length=6, max_length=300)


class ReplayEvidence(BaseModel):
    replay_delay_ms: int = Field(ge=0, le=30000)
