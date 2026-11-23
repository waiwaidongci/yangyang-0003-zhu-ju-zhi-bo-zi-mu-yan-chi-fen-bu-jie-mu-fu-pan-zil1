"""Issue immutable cue sample exports only from signed quality evidence."""
from hashlib import sha256

from fastapi import HTTPException

from quality_checks import cue_rows, validate_current
from subtitles import repair_for, segment
from track_vtt import file_name, webvtt


def require_source(cx, row):
    if not row["recording_ref"]:
        raise HTTPException(409, "有源录音的节目段才能编制字幕轨")
    repair = repair_for(cx, row["code"])
    if repair and repair["status"] != "accepted":
        raise HTTPException(409, "补字幕工作包须签收后才能编制字幕轨")


def reviewed_snapshot(cx, row, quality_id):
    current = cx.execute(
        "SELECT * FROM caption_quality_review WHERE id=%s AND segment_code=%s",
        (quality_id, row["code"])
    ).fetchone()
    if not current or not current["reviewed_at"]:
        raise HTTPException(409, "须关联本节目段已签的字幕质检单")
    cues = cue_rows(cx, row["code"])
    validate_current(row, cues, current)
    return cues


def prepare_track(cx, code, quality_id, preparer):
    row = segment(cx, code, lock=True)
    require_source(cx, row)
    cues = reviewed_snapshot(cx, row, quality_id)
    body = webvtt(cues)
    fingerprint = sha256(body.encode()).hexdigest()
    version = cx.execute(
        "SELECT coalesce(max(version),0)+1 AS next FROM caption_track WHERE segment_code=%s", (code,)
    ).fetchone()["next"]
    cx.execute(
        """INSERT INTO caption_track(segment_code,version,quality_id,file_name,vtt_body,track_hash,prepared_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (code, version, quality_id, file_name(code, version), body, fingerprint, preparer)
    )
    return track_for(cx, code, version)


def track_for(cx, code, version, include_body=False):
    item = cx.execute(
        "SELECT * FROM caption_track WHERE segment_code=%s AND version=%s", (code, version)
    ).fetchone()
    if not item:
        raise HTTPException(404, "找不到该字幕轨版本")
    if not include_body:
        item.pop("vtt_body")
    return item


def sign_track(cx, code, version, signer):
    row = segment(cx, code, lock=True)
    track = track_for(cx, code, version)
    if track["signed_at"]:
        return track
    require_source(cx, row)
    reviewed_snapshot(cx, row, track["quality_id"])
    cx.execute(
        """UPDATE caption_track SET signed_by=%s,signed_at=now()
           WHERE segment_code=%s AND version=%s""", (signer, code, version)
    )
    return track_for(cx, code, version)
