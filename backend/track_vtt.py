"""Serialize signed cue timing and plain transcript as a deterministic WebVTT file."""
from html import escape
import re


def timecode(offset_ms):
    seconds, millis = divmod(offset_ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def text_field(text):
    return escape(" ".join(text.split()), quote=False)


def webvtt(cues):
    entries = ["WEBVTT", ""]
    for cue in cues:
        start = cue["on_air_ms"]
        end = start + cue["display_ms"]
        entries.extend([
            str(cue["cue_no"]),
            f"{timecode(start)} --> {timecode(end)}",
            f"<v {text_field(cue['speaker'])}>{text_field(cue['excerpt'])}",
            "",
        ])
    return "\n".join(entries) + "\n"


def file_name(code, version):
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", code)[:64] or "caption"
    return f"{safe}-sample-v{version}.vtt"
