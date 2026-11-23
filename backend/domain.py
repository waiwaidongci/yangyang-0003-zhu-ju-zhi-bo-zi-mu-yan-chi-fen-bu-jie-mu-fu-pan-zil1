"""API for the programme rundown, alignment, diagnosis and repair desk."""
from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core import db, enqueue, require
from sla_service import compute_release_segment, refresh_pending_release
from subtitles import (
    allow_alignment, anchors_for, build_diagnosis, change_repair, open_repair, repair_for,
    save_anchor, segment,
)

router = APIRouter(prefix="/api")
read = Depends(require("operator", "reviewer", "viewer"))
operate = Depends(require("operator"))
review = Depends(require("reviewer"))


class Anchor(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cue_no: int = Field(ge=1, le=100)
    spoken_ms: int = Field(ge=0)
    on_air_ms: int = Field(ge=0)
    excerpt: str = Field(min_length=1, max_length=100)


class Recording(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recording_ref: str = Field(min_length=1, max_length=160, pattern=r"^[^/\\]+\.(wav|flac)$")


class RepairAction(StrEnum):
    START = "start"
    SUBMIT = "submit"
    RETURN = "return"
    ACCEPT = "accept"


class EditRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    corrected_ref: str | None = Field(default=None, max_length=160, pattern=r"^[^/\\]+\.(vtt|srt)$")
    note: str | None = Field(default=None, max_length=400)


@router.get("/rundown")
def rundown(user=read):
    with db() as cx:
        return cx.execute(
            """SELECT s.code, s.program, s.segment_title, s.rundown_start, s.recording_ref,
                      s.duration_ms, s.expected_anchors, s.sla_ms, s.diagnosis_revision,
                      s.anchor_revision, r.status AS repair_status,
                      (SELECT count(*) FROM cue_anchor a WHERE a.segment_code=s.code) AS cue_count
               FROM live_segment s LEFT JOIN caption_repair r ON r.segment_code=s.code
               ORDER BY s.rundown_start, s.code"""
        ).fetchall()


@router.get("/rundown/{code}")
def segment_workspace(code: str, user=read):
    with db() as cx:
        return {
            "segment": segment(cx, code),
            "anchors": anchors_for(cx, code),
            "repair": repair_for(cx, code),
        }


@router.put("/rundown/{code}/recording")
def attach_recording(code: str, recording: Recording, user=operate):
    with db() as cx:
        segment(cx, code, lock=True)
        allow_alignment(cx, code)
        return cx.execute(
            "UPDATE live_segment SET recording_ref=%s WHERE code=%s RETURNING recording_ref",
            (recording.recording_ref, code)
        ).fetchone()


@router.put("/rundown/{code}/alignment")
def put_anchor(code: str, anchor: Anchor, user=operate):
    with db() as cx:
        refresh_pending_release(cx, code)
        save_anchor(cx, code, anchor)
        return {"cue_no": anchor.cue_no}


@router.post("/rundown/{code}/diagnosis", status_code=202)
def submit_diagnosis(code: str, user=operate):
    with db() as cx:
        item = segment(cx, code, lock=True)
        if len(anchors_for(cx, code)) < 5:
            raise HTTPException(409, "至少需对齐 5 个时间码锚点")
        job = enqueue(cx, "caption-ecdf", {"code": code, "revision": item["anchor_revision"]})
        return {"job_id": job}


@router.post("/rundown/{code}/repair", status_code=201)
def dispatch_repair(code: str, user=operate):
    with db() as cx:
        return open_repair(cx, code)


@router.post("/rundown/{code}/repair/{action}")
def apply_repair_action(code: str, action: RepairAction, data: EditRequest,
                        user=Depends(require("operator", "reviewer"))):
    role = "operator" if action in (RepairAction.START, RepairAction.SUBMIT) else "reviewer"
    if user["role"] != role:
        raise HTTPException(403, "当前角色无权处理该步")
    with db() as cx:
        return change_repair(cx, code, action, data.corrected_ref, data.note, user["email"])


def run_job(cx, kind, payload):
    if kind == "caption-ecdf":
        return build_diagnosis(cx, payload["code"], payload["revision"])
    if kind == "sla-release-segment":
        return compute_release_segment(cx, payload["release_id"], payload["code"])
    raise ValueError(f"Unknown caption job: {kind}")


def seed(cx):
    fixtures = [
        ("AFTER-01", "街巷开麦", "手艺人圆桌", "19:30", 120000, 8, 1800, None,
         [(8000, 1100, "先把茶盘端过来"), (25000, 1200, "我是跟外公学的"),
          (51000, 1500, "这一道要慢慢收"), (83000, 2900, "那时候还没有这条街"),
          (93000, 4200, "石阶底下全是雨水"), (107000, 5200, "后来我们再开一间铺")]),
        ("AFTER-02", "街巷开麦", "街坊来信", "19:32", 90000, 5, 1800, "letters-master.wav",
         [(10000, 850, "第一封来自和平街"), (21000, 900, "她记得那把木椅"),
          (40000, 880, "桥下以前有菜市"), (62000, 1150, "我想留一段录音"),
          (79000, 900, "下次仍在桥边见")]),
        ("AFTER-03", "街巷开麦", "片尾值守", "19:34", 45000, 5, 1800, "outro-master.wav",
         [(8000, 2200, "老街音乐会周末开场"), (15000, 2500, "走路的话从东门进"),
          (25000, 2600, "也可以预约手语席"), (32000, 2800, "演出后有现场采访"),
          (38000, 2400, "今晚的节目到这里")]),
    ]
    for code, program, title, start, duration, expected, sla, recording, anchors in fixtures:
        inserted = cx.execute(
            """INSERT INTO live_segment(code,program,segment_title,rundown_start,duration_ms,
                                         expected_anchors,sla_ms,recording_ref,anchor_revision)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1) ON CONFLICT DO NOTHING RETURNING code""",
            (code, program, title, start, duration, expected, sla, recording)
        ).fetchone()
        if not inserted:
            continue
        for number, (spoken, offset, excerpt) in enumerate(anchors, 1):
            cx.execute(
                """INSERT INTO cue_anchor(segment_code,cue_no,spoken_ms,on_air_ms,excerpt)
                   VALUES (%s,%s,%s,%s,%s)""",
                (code, number, spoken, spoken + offset, excerpt)
            )
        build_diagnosis(cx, code, 1)
        if code == "AFTER-03":
            open_repair(cx, code)
