"""Read, prepare, sign and download versioned WebVTT evidence tracks."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from core import db, require
from track_service import prepare_track, sign_track, track_for

router = APIRouter(prefix="/api/rundown")


class TrackDraft(BaseModel):
    quality_id: int = Field(gt=0)


@router.get("/{code}/tracks")
def list_tracks(code: str, user=Depends(require())):
    with db() as cx:
        rows = cx.execute(
            """SELECT segment_code,version,quality_id,file_name,track_hash,prepared_by,signed_by,signed_at,created_at
               FROM caption_track WHERE segment_code=%s ORDER BY version DESC""", (code,)
        ).fetchall()
        choices = cx.execute(
            """SELECT id FROM caption_quality_review WHERE segment_code=%s AND reviewed_at IS NOT NULL
               ORDER BY id DESC""", (code,)
        ).fetchall()
        return {"tracks": rows, "quality_choices": choices}


@router.post("/{code}/tracks", status_code=201)
def create_track(code: str, data: TrackDraft, user=Depends(require("operator"))):
    with db() as cx:
        return prepare_track(cx, code, data.quality_id, user["email"])


@router.post("/{code}/tracks/{version}/sign")
def sign_vtt(code: str, version: int, user=Depends(require("reviewer"))):
    with db() as cx:
        return sign_track(cx, code, version, user["email"])


@router.get("/{code}/tracks/{version}/file")
def export_vtt(code: str, version: int, user=Depends(require())):
    with db() as cx:
        item = track_for(cx, code, version, include_body=True)
    if not item["signed_at"]:
        raise HTTPException(409, "字幕轨尚未签发")
    return Response(item["vtt_body"], media_type="text/vtt", headers={
        "Content-Disposition": f'attachment; filename="{item["file_name"]}"'
    })
