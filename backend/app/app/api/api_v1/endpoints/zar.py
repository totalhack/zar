from collections import defaultdict
from typing import Generator, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.inspection import inspect
from tlbx import st, pp, json

from app import models
from app.schemas.zar import *
from app.api import deps
from app.core.config import settings
from app.utils import extract_header_params

router = APIRouter()


def print_request(headers, body):
    print("---- Headers")
    pp(headers)
    print("---- Body")
    pp(body)


@router.post("/page", response_model=Dict[str, Any])
def page(
    body: PageRequestBody, request: Request, db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Store page event"""
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)
    body["properties"] = body["properties"] or {}
    zar = body["properties"].get("zar", {})
    page_obj = models.Page(
        vid=zar.get("vid", {}).get("id", None),
        sid=zar.get("sid", {}).get("id", None),
        cid=zar.get("cid", {}).get("id", None),
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
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)
    body["properties"] = body["properties"] or {}
    zar = body["properties"].get("zar", {})
    track_obj = models.Track(
        event=body["event"],
        vid=zar.get("vid", {}).get("id", None),
        sid=zar.get("sid", {}).get("id", None),
        cid=zar.get("cid", {}).get("id", None),
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


@router.get("/ok")
def ok(request: Request) -> str:
    """Health check"""
    return "OK"

