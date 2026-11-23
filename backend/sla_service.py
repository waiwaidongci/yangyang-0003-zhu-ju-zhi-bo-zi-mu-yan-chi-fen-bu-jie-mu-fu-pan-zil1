"""Stage a programme-wide time-limit change and switch it over atomically."""
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from core import enqueue
from subtitles import anchors_for, segment
from timing import diagnose

JOB_KIND = "sla-release-segment"


def release_view(cx, release):
    segments = cx.execute(
        """SELECT segment_code,anchor_revision,status,error
           FROM sla_release_segment WHERE release_id=%s ORDER BY segment_code""",
        (release["id"],)
    ).fetchall()
    done = sum(row["status"] == "done" for row in segments)
    return {"release": release | {"done": done, "total": len(segments)}, "segments": segments}


def latest_release(cx, program):
    row = cx.execute(
        "SELECT * FROM sla_release WHERE program=%s ORDER BY id DESC LIMIT 1", (program,)
    ).fetchone()
    return release_view(cx, row) if row else {"release": None, "segments": []}


def enqueue_segments(cx, release_id, codes):
    for code in codes:
        enqueue(cx, JOB_KIND, {"release_id": release_id, "code": code})


def request_adjustment(cx, program, sla_ms, request_key, email):
    segments = cx.execute(
        "SELECT code,anchor_revision FROM live_segment WHERE program=%s ORDER BY code", (program,)
    ).fetchall()
    if not segments:
        raise HTTPException(404, "节目不存在")
    existing = cx.execute(
        "SELECT * FROM sla_release WHERE program=%s AND request_key=%s", (program, request_key)
    ).fetchone()
    if existing:
        return release_view(cx, existing)
    active = cx.execute(
        "SELECT * FROM sla_release WHERE program=%s AND status='computing'", (program,)
    ).fetchone()
    if active:
        if active["sla_ms"] != sla_ms:
            raise HTTPException(409, "已有进行中的时限调整，待其结束后再发起")
        pending = [row["segment_code"] for row in
                   cx.execute("SELECT segment_code FROM sla_release_segment WHERE release_id=%s AND status='pending'",
                              (active["id"],)).fetchall()]
        enqueue_segments(cx, active["id"], pending)
        return release_view(cx, active)
    release = cx.execute(
        """INSERT INTO sla_release(program,sla_ms,request_key,requested_by)
           VALUES (%s,%s,%s,%s) ON CONFLICT (program,request_key) DO NOTHING RETURNING *""",
        (program, sla_ms, request_key, email)
    ).fetchone()
    if not release:
        return latest_release(cx, program)
    for row in segments:
        cx.execute(
            """INSERT INTO sla_release_segment(release_id,segment_code,anchor_revision)
               VALUES (%s,%s,%s)""",
            (release["id"], row["code"], row["anchor_revision"])
        )
    enqueue_segments(cx, release["id"], [row["code"] for row in segments])
    return release_view(cx, release)


def refresh_pending_release(cx, code):
    """An anchor moved: drop the staged diagnosis so it is recomputed from the latest anchors."""
    release = cx.execute(
        """SELECT r.* FROM sla_release r JOIN live_segment s ON s.program=r.program
           WHERE s.code=%s AND r.status='computing' FOR UPDATE OF r""",
        (code,)
    ).fetchone()
    if not release:
        return
    stale = cx.execute(
        """UPDATE sla_release_segment SET status='pending',diagnosis=NULL,error=NULL
           WHERE release_id=%s AND segment_code=%s AND status='done' RETURNING segment_code""",
        (release["id"], code)
    ).fetchone()
    if stale:
        enqueue(cx, JOB_KIND, {"release_id": release["id"], "code": code})


def compute_release_segment(cx, release_id, code):
    release = cx.execute(
        "SELECT * FROM sla_release WHERE id=%s FOR UPDATE", (release_id,)
    ).fetchone()
    if not release or release["status"] != "computing":
        return {"skipped": True}
    current = segment(cx, code)
    try:
        result = diagnose(anchors_for(cx, code), current["duration_ms"],
                          current["expected_anchors"], release["sla_ms"])
    except ValueError as exc:
        cx.execute(
            """UPDATE sla_release_segment SET status='failed',error=%s
               WHERE release_id=%s AND segment_code=%s""",
            (str(exc), release_id, code)
        )
        cx.execute(
            "UPDATE sla_release SET status='failed',error=%s WHERE id=%s",
            (f"{code}: {exc}", release_id)
        )
        return {"failed": str(exc)}
    cx.execute(
        """UPDATE sla_release_segment SET status='done',diagnosis=%s,anchor_revision=%s,error=NULL
           WHERE release_id=%s AND segment_code=%s""",
        (Jsonb(result), current["anchor_revision"], release_id, code)
    )
    publish_if_ready(cx, release)
    return {"computed": code, "revision": current["anchor_revision"]}


def publish_if_ready(cx, release):
    segments = cx.execute(
        "SELECT * FROM sla_release_segment WHERE release_id=%s", (release["id"],)
    ).fetchall()
    current = {
        row["code"]: row["anchor_revision"]
        for row in cx.execute(
            "SELECT code,anchor_revision FROM live_segment WHERE code=ANY(%s) FOR UPDATE",
            ([row["segment_code"] for row in segments],)
        ).fetchall()
    }
    for row in segments:
        if row["status"] == "done" and row["anchor_revision"] != current[row["segment_code"]]:
            cx.execute(
                """UPDATE sla_release_segment SET status='pending',diagnosis=NULL
                   WHERE release_id=%s AND segment_code=%s""",
                (release["id"], row["segment_code"])
            )
            enqueue(cx, JOB_KIND, {"release_id": release["id"], "code": row["segment_code"]})
            row["status"] = "pending"
    if any(row["status"] != "done" for row in segments):
        return False
    for row in segments:
        cx.execute(
            "UPDATE live_segment SET sla_ms=%s,diagnosis=%s,diagnosis_revision=%s WHERE code=%s",
            (release["sla_ms"], Jsonb(row["diagnosis"]), row["anchor_revision"], row["segment_code"])
        )
    cx.execute(
        "UPDATE sla_release SET status='published',published_at=now() WHERE id=%s",
        (release["id"],)
    )
    return True
