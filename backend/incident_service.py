"""Require complete, in-budget playback retests before signing incident closeout."""
from fastapi import HTTPException

from subtitles import segment
from track_service import reviewed_snapshot, track_for


def for_incident(cx, code, incident_id, lock=False):
    row = cx.execute(
        "SELECT * FROM delay_incident WHERE segment_code=%s AND id=%s" + (" FOR UPDATE" if lock else ""),
        (code, incident_id)
    ).fetchone()
    if not row:
        raise HTTPException(404, "找不到该复盘事件")
    return row


def current_evidence(cx, incident):
    replays = cx.execute(
        "SELECT cue_no,replay_delay_ms FROM delay_retest WHERE incident_id=%s ORDER BY cue_no",
        (incident["id"],)
    ).fetchall()
    recorded = {row["cue_no"]: row["replay_delay_ms"] for row in replays}
    return {"checks": replays,
            "missing": [cue for cue in incident["impacted_cues"] if cue not in recorded],
            "late": [cue for cue, delay in recorded.items() if delay > incident["sla_ms"]]}


def open_incident(cx, code, data):
    row = segment(cx, code, lock=True)
    track = track_for(cx, code, data.track_version)
    if not track["signed_at"]:
        raise HTTPException(409, "仅可用已签发的字幕样本轨作复测依据")
    if row["diagnosis_revision"] != row["anchor_revision"] or not row["diagnosis"]:
        raise HTTPException(409, "开复盘前先计算当前上屏延迟")
    reviewed_snapshot(cx, row, track["quality_id"])
    delayed = row["diagnosis"]["late_cues"]
    if not delayed:
        raise HTTPException(409, "诊断未发现时限违例")
    result = cx.execute(
        """INSERT INTO delay_incident(segment_code,source_revision,track_version,sla_ms,
                                      impacted_cues,cause,countermeasure)
           VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *""",
        (code, row["diagnosis_revision"], data.track_version, row["sla_ms"], delayed, data.cause, data.countermeasure)
    ).fetchone()
    if not result:
        raise HTTPException(409, "该诊断版本和字幕轨已有复盘事件")
    return result


def add_replay(cx, code, incident_id, cue_no, delay):
    row = for_incident(cx, code, incident_id, lock=True)
    if row["closed_at"] or cue_no not in row["impacted_cues"]:
        raise HTTPException(409, "事件已结案或该锚点不在复测范围")
    return cx.execute(
        """INSERT INTO delay_retest(incident_id,cue_no,replay_delay_ms) VALUES (%s,%s,%s)
           ON CONFLICT (incident_id,cue_no) DO UPDATE SET replay_delay_ms=excluded.replay_delay_ms,
           checked_at=now() RETURNING *""", (incident_id, cue_no, delay)
    ).fetchone()


def close_incident(cx, code, incident_id, reviewer):
    row = for_incident(cx, code, incident_id, lock=True)
    if row["closed_at"]:
        return row
    evidence = current_evidence(cx, row)
    if evidence["missing"] or evidence["late"]:
        raise HTTPException(409, "仍有遗漏复测或超过上屏时限的锚点")
    return cx.execute(
        "UPDATE delay_incident SET closed_by=%s,closed_at=now() WHERE id=%s RETURNING *",
        (reviewer, incident_id)
    ).fetchone()
