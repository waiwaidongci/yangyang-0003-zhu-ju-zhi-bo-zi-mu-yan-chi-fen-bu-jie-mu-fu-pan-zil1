"""Timed sidecar marking and accessible reading-rate policy."""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SpeakerChannel(StrEnum):
    HOST = "host"
    GUEST = "guest"
    REMOTE = "remote"


class ChannelMark(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    channel: SpeakerChannel
    speaker: str = Field(min_length=1, max_length=40)
    display_ms: int = Field(ge=250, le=15000)


class QualityPolicy(BaseModel):
    max_chars_per_second: int = Field(default=16, ge=8, le=30)
