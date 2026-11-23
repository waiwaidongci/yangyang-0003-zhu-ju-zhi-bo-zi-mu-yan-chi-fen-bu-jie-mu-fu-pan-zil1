"""Persistence and workflow for recording alignment and caption re-editing."""
from enum import StrEnum

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from timing import diagnose


class RepairStatus(StrEnum):
    QUEUED = "queued"
    EDITING = "editing"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"


def segment(cx, code, lock=False):
    query = "SELECT * FROM live_segment WHERE code=%s"
    row = cx.execute(query + (" FOR UPDATE" if lock else ""), (code,)).fetchone()
    if row is None:
        raise HTTPException(404, "节目段不存在")
    return row


def anchors_for(cx, code):
    return cx.execute(
        "SELECT * FROM cue_anchor WHERE segment_code=%s ORDER BY cue_no", (code,)
    ).fetchall()


def repair_for(cx, code, required=False):
    row = cx.execute(
        "SELECT * FROM caption_repair WHERE segment_code=%s", (code,)
    ).fetchone()
    if required and row is None:
        raise HTTPException(404, "补字幕工作包不存在")
    return row


def allow_alignment(cx, code):
    row = repair_for(cx, code)
    if row and row["status"] in (RepairStatus.SUBMITTED, RepairStatus.ACCEPTED):
        raise HTTPException(409, "工作包已送审，当前时间码和录音已锁定")


def save_anchor(cx, code, anchor):
    current = segment(cx, code, lock=True)
    allow_alignment(cx, code)
    if anchor.cue_no > current["expected_anchors"]:
        raise HTTPException(422, "锚点编号超过节目单抽样计划")
    if max(anchor.spoken_ms, anchor.on_air_ms) > current["duration_ms"]:
        raise HTTPException(422, "语音或上屏时间码超出节目段")
    if cx.execute(
        "SELECT 1 FROM cue_anchor WHERE segment_code=%s AND spoken_ms=%s AND cue_no<>%s",
        (code, anchor.spoken_ms, anchor.cue_no)
    ).fetchone():
        raise HTTPException(409, "同一语音时间码已由另一个锚点占用")
    cx.execute(
        """INSERT INTO cue_anchor(segment_code,cue_no,spoken_ms,on_air_ms,excerpt)
           VALUES (%s,%s,%s,%s,%s) ON CONFLICT (segment_code,cue_no) DO UPDATE SET
           spoken_ms=excluded.spoken_ms,on_air_ms=excluded.on_air_ms,excerpt=excluded.excerpt""",
        (code, anchor.cue_no, anchor.spoken_ms, anchor.on_air_ms, anchor.excerpt)
    )
    cx.execute("UPDATE live_segment SET anchor_revision=anchor_revision+1 WHERE code=%s", (code,))


def build_diagnosis(cx, code, revision):
    current = segment(cx, code, lock=True)
    if current["anchor_revision"] != revision:
        return {"stale": True}
    result = diagnose(anchors_for(cx, code), current["duration_ms"],
                      current["expected_anchors"], current["sla_ms"])
    cx.execute(
        "UPDATE live_segment SET diagnosis=%s,diagnosis_revision=%s WHERE code=%s",
        (Jsonb(result), revision, code)
    )
    return result


def open_repair(cx, code):
    current = segment(cx, code, lock=True)
    if not current["diagnosis"] or current["anchor_revision"] != current["diagnosis_revision"]:
        raise HTTPException(409, "先生成与当前锚点版本一致的延迟诊断")
    if repair_for(cx, code):
        raise HTTPException(409, "该节目段已有补字幕工作包")
    problem = current["diagnosis"]["repair_range"]
    if problem is None:
        raise HTTPException(409, "暂无超时字幕需要返修")
    return cx.execute(
        """INSERT INTO caption_repair(segment_code,start_ms,end_ms)
           VALUES (%s,%s,%s) RETURNING *""",
        (code, *problem)
    ).fetchone()


def change_repair(cx, code, action, corrected_ref, note, reviewer):
    current = segment(cx, code, lock=True)
    repair = repair_for(cx, code, required=True)
    target = {
        (RepairStatus.QUEUED, "start"): RepairStatus.EDITING,
        (RepairStatus.EDITING, "submit"): RepairStatus.SUBMITTED,
        (RepairStatus.SUBMITTED, "return"): RepairStatus.EDITING,
        (RepairStatus.SUBMITTED, "accept"): RepairStatus.ACCEPTED,
    }.get((repair["status"], action))
    if not target:
        raise HTTPException(409, "当前工作包状态不允许该操作")
    repair_range = None
    if action in ("submit", "accept"):
        if not current["recording_ref"]:
            raise HTTPException(409, "未挂接原始录音，无法核对补字幕")
        count = len(anchors_for(cx, code))
        if count * 5 < current["expected_anchors"] * 4:
            raise HTTPException(409, "锚点覆盖低于 80%，请补齐复核锚点")
        if action == "submit":
            if not corrected_ref or corrected_ref == current["recording_ref"]:
                raise HTTPException(422, "请填写与源录音不同的补字幕文件")
            if current["anchor_revision"] != current["diagnosis_revision"]:
                raise HTTPException(409, "锚点已调整，请先重算返修时间码")
            repair_range = current["diagnosis"]["repair_range"]
            if repair_range is None:
                raise HTTPException(409, "当前锚点未检出超时字幕，请核对原始直播锚点")
    if action == "return" and not note:
        raise HTTPException(422, "请填写退回说明")
    return cx.execute(
        """UPDATE caption_repair SET status=%s,
              start_ms=COALESCE(%s, start_ms),
              end_ms=COALESCE(%s, end_ms),
              corrected_ref=COALESCE(%s, corrected_ref),
              review_note=COALESCE(%s, review_note),
              reviewed_by=COALESCE(%s, reviewed_by),
              submitted_at=CASE WHEN %s='submit' THEN now() ELSE submitted_at END,
              accepted_at=CASE WHEN %s='accept' THEN now() ELSE accepted_at END
           WHERE segment_code=%s RETURNING *""",
        (target, *(repair_range or (None, None)), corrected_ref if action == "submit" else None,
         note if action in ("return", "accept") else None,
         reviewer if action in ("return", "accept") else None, action, action, code)
    ).fetchone()
