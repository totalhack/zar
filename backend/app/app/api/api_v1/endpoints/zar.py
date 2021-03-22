from typing import Generator, Dict, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.inspection import inspect
from tlbx import st, json

from app import models
from app.schemas.zar import *
from app.api import deps
from app.core.config import settings
from app.utils import print_request, extract_header_params, create_zar_dict, get_zar_ids

router = APIRouter()


@router.post("/page", response_model=Dict[str, Any])
def page(
    body: PageRequestBody,
    request: Request,
    db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
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


@router.get("/noscript", response_model=Dict[str, Any])
def noscript(
    request: Request,
    db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    if settings.DEBUG:
        print_request(request.headers, None)
    headers = extract_header_params(request.headers)

    zar = create_zar_dict()
    props = dict(
        noscript=True,
        url=str(request.url),
        zar=zar,
    )

    vid, sid, cid = get_zar_ids(zar)
    page_obj = models.Page(
        vid=vid,
        sid=sid,
        cid=cid,
        uid=None,
        host=headers["host"],
        ip=headers["ip"],
        user_agent=headers["user_agent"],
        referer=headers["referer"],
        properties=json.dumps(props),
    )
    db.add(page_obj)
    db.commit()
    pk = inspect(page_obj).identity
    pk = pk[0] if pk else None
    return dict(id=pk)


@router.get("/ok")
def ok(request: Request) -> str:
    return "OK"
