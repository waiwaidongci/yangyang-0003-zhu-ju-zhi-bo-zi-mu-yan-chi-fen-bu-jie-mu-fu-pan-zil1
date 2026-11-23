"""Duty-desk endpoints for programme-wide on-screen time-limit releases."""
from fastapi import APIRouter, Depends

from core import db, require
from sla_schema import SlaAdjustment
from sla_service import latest_release, request_adjustment

router = APIRouter(prefix="/api/programs")


@router.get("/{program}/sla")
def release_status(program: str, user=Depends(require())):
    with db() as cx:
        return latest_release(cx, program)


@router.post("/{program}/sla", status_code=202)
def adjust_sla(program: str, data: SlaAdjustment, user=Depends(require("operator"))):
    with db() as cx:
        return request_adjustment(cx, program, data.sla_ms, data.request_key, user["email"])
