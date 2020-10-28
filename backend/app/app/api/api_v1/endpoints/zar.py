from collections import defaultdict
from typing import Generator, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.inspection import inspect
from tlbx import st, pp, json

from app import models
from app.schemas.zar import *
from app.api import deps

router = APIRouter()


def extract_header_params(headers):
    host = headers.get("x-forwarded-host", None) or headers["host"]
    ip = (
        headers.get("x-forwarded-for", None)
        or headers.get("x-real-ip", None)
        or headers.get("forwarded", None)
    )
    user_agent = headers["user-agent"]
    referer = headers["referer"]
    return dict(host=host, ip=ip, user_agent=user_agent, referer=referer)


@router.post("/page", response_model=Dict[str, Any])
def page(
    body: PageRequestBody, request: Request, db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Store page event"""
    body = dict(body)
    pp(body)
    headers = extract_header_params(request.headers)
    body["zar"] = body["zar"] or {}
    body["properties"] = body["properties"] or {}
    page_obj = models.Page(
        vid=body["zar"].get("vid", None),
        sid=body["zar"].get("sid", None),
        cid=body["zar"].get("cid", None),
        uid=body["userId"],
        host=headers["host"],
        ip=headers["ip"],
        user_agent=headers["user_agent"],
        referer=headers["referer"],
        properties=json.dumps(body["properties"]),
    )
    db.add(page_obj)
    db.commit()
    pk = inspect(page_obj).identity
    pk = pk[0] if pk else None
    return dict(id=pk)


@router.post("/track", response_model=Dict[str, Any])
def track(
    body: TrackRequestBody, request: Request, db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Store track event"""
    body = dict(body)
    headers = extract_header_params(request.headers)
    body["zar"] = body["zar"] or {}
    body["properties"] = body["properties"] or {}
    track_obj = models.Track(
        event=body["event"],
        vid=body["zar"].get("vid", None),
        sid=body["zar"].get("sid", None),
        cid=body["zar"].get("cid", None),
        uid=body["userId"],
        host=headers["host"],
        ip=headers["ip"],
        user_agent=headers["user_agent"],
        referer=headers["referer"],
        properties=json.dumps(body["properties"]),
    )
    db.add(track_obj)
    db.commit()
    pk = inspect(track_obj).identity
    pk = pk[0] if pk else None
    return dict(id=pk)

