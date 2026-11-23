"""Input contract for programme-wide on-screen time-limit adjustment."""
from pydantic import BaseModel, ConfigDict, Field


class SlaAdjustment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sla_ms: int = Field(ge=250, le=8000)
    request_key: str = Field(min_length=8, max_length=80)
