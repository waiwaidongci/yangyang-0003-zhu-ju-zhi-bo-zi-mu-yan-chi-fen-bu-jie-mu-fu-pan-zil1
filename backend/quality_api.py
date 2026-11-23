"""Operator sheet for speaker marks and independent cue quality approval."""
from fastapi import APIRouter, Depends

from core import db, require
from quality_checks import cue_rows, digest, save_mark, scan, sign_quality
from quality_schema import ChannelMark, QualityPolicy
from subtitles import segment

router = APIRouter(prefix="/api/rundown")


@router.get("/{code}/quality")
def quality_sheet(code: str, user=Depends(require())):
    with db() as cx:
        row = segment(cx, code)
        cues = cue_rows(cx, code)
        scans = cx.execute(
            "SELECT * FROM caption_quality_review WHERE segment_code=%s ORDER BY id DESC", (code,)
        ).fetchall()
        for review in scans:
            review["stale"] = review["input_hash"] != digest(row, cues, review["max_chars_per_second"])
        return {"cues": cues, "scans": scans}


@router.put("/{code}/quality/marks/{cue_no}")
def mark_cue(code: str, cue_no: int, data: ChannelMark, user=Depends(require("operator"))):
    with db() as cx:
        return save_mark(cx, code, cue_no, data)


@router.post("/{code}/quality/scan", status_code=201)
def run_quality(code: str, data: QualityPolicy, user=Depends(require("operator"))):
    with db() as cx:
        return scan(cx, code, data.max_chars_per_second)


@router.post("/{code}/quality/{review_id}/sign")
def approve_quality(code: str, review_id: int, user=Depends(require("reviewer"))):
    with db() as cx:
        return sign_quality(cx, code, review_id, user["email"])
