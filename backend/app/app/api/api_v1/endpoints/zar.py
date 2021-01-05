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


def get_zar_ids(zar):
    vid_dict = zar.get("vid", {})
    sid_dict = zar.get("sid", {})
    cid_dict = zar.get("cid", {})
    vid = vid_dict.get("id", None) if vid_dict else None
    sid = sid_dict.get("id", None) if sid_dict else None
    cid = cid_dict.get("id", None) if cid_dict else None
    return vid, sid, cid


@router.post("/page", response_model=Dict[str, Any])
def page(
    body: PageRequestBody,
    request: Request,
    db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Store page event"""
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)
    body["properties"] = body["properties"] or {}
    zar = body["properties"].get("zar", {}) or {}
    vid, sid, cid = get_zar_ids(zar)
    page_obj = models.Page(
        vid=vid,
        sid=sid,
        cid=cid,
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
    body: TrackRequestBody,
    request: Request,
    db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    """Store track event"""
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)

    body["properties"] = body["properties"] or {}
    zar = body["properties"].get("zar", {})
    vid, sid, cid = get_zar_ids(zar)
    if "zar" in body["properties"]:
        # Can get this data from the page/visit info
        del body["properties"]["zar"]

    track_obj = models.Track(
        event=body["event"],
        vid=vid,
        sid=sid,
        cid=cid,
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
