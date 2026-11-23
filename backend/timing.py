"""Estimate subtitle timing from hand-aligned timestamps in one programme segment."""
from collections import Counter
from math import ceil


def diagnose(anchors, duration_ms, expected_anchors, sla_ms):
    if len(anchors) < 5:
        raise ValueError("至少需对齐 5 个时间码锚点")
    offsets = sorted(a["on_air_ms"] - a["spoken_ms"] for a in anchors)
    count = len(offsets)
    late = [a for a in anchors if a["on_air_ms"] - a["spoken_ms"] > sla_ms]
    windows = [0, 0, 0]
    for anchor in late:
        windows[min(2, anchor["spoken_ms"] * 3 // duration_ms)] += 1

    p50, p90 = (offsets[ceil(count * q) - 1] for q in (.5, .9))
    if len(late) >= 2 and max(windows) * 4 >= len(late) * 3:
        pattern = "local_tail"
    elif len(late) * 2 >= count:
        pattern = "systematic"
    elif late:
        pattern = "sporadic"
    else:
        pattern = "on_time"

    cumulative = 0
    ecdf = []
    for offset, frequency in sorted(Counter(offsets).items()):
        cumulative += frequency
        ecdf.append({"offset_ms": offset, "share": cumulative / count})
    return {
        "count": count, "coverage": count / expected_anchors,
        "p50": p50, "p90": p90, "late_count": len(late), "late_rate": len(late) / count,
        "pattern": pattern, "late_windows": windows, "ecdf": ecdf,
        "late_cues": [a["cue_no"] for a in late],
        "repair_range": [
            max(0, min(a["spoken_ms"] for a in late) - 2000),
            min(duration_ms, max(a["spoken_ms"] for a in late) + 2000),
        ] if late else None,
    }
