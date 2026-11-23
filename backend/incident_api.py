"""Return after-action checks beside the archived SLA evidence."""
from fastapi import APIRouter, Depends

from core import db, require
from incident_schema import IncidentDraft, ReplayEvidence
from incident_service import add_replay, close_incident, current_evidence, open_incident

router = APIRouter(prefix="/api/rundown")


@router.get("/{code}/incidents")
def incident_board(code: str, user=Depends(require())):
    with db() as cx:
        rows = cx.execute("SELECT * FROM delay_incident WHERE segment_code=%s ORDER BY id DESC", (code,)).fetchall()
        tracks = cx.execute(
            "SELECT version FROM caption_track WHERE segment_code=%s AND signed_at IS NOT NULL ORDER BY version DESC",
            (code,)
        ).fetchall()
        return {"incidents": [row | current_evidence(cx, row) for row in rows], "tracks": tracks}


@router.post("/{code}/incidents", status_code=201)
def register_incident(code: str, data: IncidentDraft, user=Depends(require("operator"))):
    with db() as cx:
        return open_incident(cx, code, data)


@router.put("/{code}/incidents/{incident_id}/retest/{cue_no}")
def record_replay(code: str, incident_id: int, cue_no: int, data: ReplayEvidence, user=Depends(require("operator"))):
    with db() as cx:
        return add_replay(cx, code, incident_id, cue_no, data.replay_delay_ms)


@router.post("/{code}/incidents/{incident_id}/close")
def conclude(code: str, incident_id: int, user=Depends(require("reviewer"))):
    with db() as cx:
        return close_incident(cx, code, incident_id, user["email"])
