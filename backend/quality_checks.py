"""Sign an exact cue snapshot, preserving the measurements reviewed for delivery."""
from hashlib import sha256
import json

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from subtitles import segment


def cue_rows(cx, code):
    return cx.execute(
        """SELECT a.*,m.channel,m.speaker,m.display_ms FROM cue_anchor a
           LEFT JOIN cue_channel_mark m USING (segment_code,cue_no)
           WHERE a.segment_code=%s ORDER BY a.on_air_ms,a.cue_no""", (code,)
    ).fetchall()


def digest(row, cues, threshold):
    fields = ("cue_no", "spoken_ms", "on_air_ms", "excerpt", "channel", "speaker", "display_ms")
    content = [row["duration_ms"], row["anchor_revision"], row["recording_ref"], threshold,
               [[cue[field] for field in fields] for cue in cues]]
    return sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()


def evaluate(cues, duration_ms, threshold):
    marks = []
    crowding_until = 0
    for cue in cues:
        issues = []
        rate = None
        if not cue["speaker"]:
            issues.append("missing_mark")
        else:
            text_length = sum(not char.isspace() for char in cue["excerpt"] + cue["speaker"] + "：")
            rate = round(text_length * 1000 / cue["display_ms"], 3)
            if text_length * 1000 > threshold * cue["display_ms"]:
                issues.append("crowded_text")
            end = cue["on_air_ms"] + cue["display_ms"]
            if end > duration_ms:
                issues.append("beyond_segment")
            if cue["on_air_ms"] < crowding_until:
                issues.append("overlap")
            crowding_until = max(crowding_until, end)
        marks.append({"cue_no": cue["cue_no"], "chars_per_second": rate, "issues": issues})
    return {"marks": marks, "failed": sum(bool(mark["issues"]) for mark in marks),
            "has_cues": bool(cues)}


def save_mark(cx, code, cue_no, payload):
    segment(cx, code, lock=True)
    if not cx.execute(
        "SELECT 1 FROM cue_anchor WHERE segment_code=%s AND cue_no=%s", (code, cue_no)
    ).fetchone():
        raise HTTPException(404, "未找到锚点，先完成时间码登记")
    return cx.execute(
        """INSERT INTO cue_channel_mark VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (segment_code,cue_no) DO UPDATE SET channel=excluded.channel,
           speaker=excluded.speaker,display_ms=excluded.display_ms RETURNING *""",
        (code, cue_no, payload.channel, payload.speaker, payload.display_ms)
    ).fetchone()


def scan(cx, code, threshold):
    row = segment(cx, code, lock=True)
    cues = cue_rows(cx, code)
    return cx.execute(
        """INSERT INTO caption_quality_review(segment_code,max_chars_per_second,input_hash,result)
           VALUES (%s,%s,%s,%s) RETURNING *""",
        (code, threshold, digest(row, cues, threshold), Jsonb(evaluate(cues, row["duration_ms"], threshold)))
    ).fetchone()


def validate_current(row, cues, review):
    if review["input_hash"] != digest(row, cues, review["max_chars_per_second"]):
        raise HTTPException(409, "源录音、锚点或标注已更新，须重检")
    if not review["result"]["has_cues"] or review["result"]["failed"]:
        raise HTTPException(409, "锚点屏显有未处理的问题")


def sign_quality(cx, code, review_id, email):
    row = segment(cx, code, lock=True)
    review = cx.execute(
        "SELECT * FROM caption_quality_review WHERE segment_code=%s AND id=%s FOR UPDATE",
        (code, review_id)
    ).fetchone()
    if not review:
        raise HTTPException(404, "找不到本段质检单")
    validate_current(row, cue_rows(cx, code), review)
    if review["reviewed_at"]:
        return review
    return cx.execute(
        """UPDATE caption_quality_review SET reviewed_by=%s,reviewed_at=now()
           WHERE id=%s RETURNING *""", (email, review_id)
    ).fetchone()
