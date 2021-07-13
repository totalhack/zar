from typing import Generator, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import insert
from sqlalchemy.inspection import inspect
from tlbx import st, json, warn, error

from app import models
from app.schemas.zar import (
    PageRequestBody,
    TrackRequestBody,
    TrackCallRequestBody,
    NumberPoolRequestBody,
)
from app.api import deps
from app.core.config import settings
from app.db.session import engine
from app.number_pool import (
    NumberPoolAPI,
    NumberPoolResponseStatus,
    NumberPoolResponseMessages,
    NumberPoolUnavailable,
    NumberPoolEmpty,
    NumberNotFound,
    NumberMaxRenewalExceeded,
)
from app.utils import print_request, extract_header_params, create_zar_dict, get_zar_ids

router = APIRouter()

# TODO add config to skip this
pool_api = None
if settings.NUMBER_POOL_ENABLED:
    try:
        pool_api = NumberPoolAPI()
    except NumberPoolUnavailable as e:
        warn(str(e))


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


@router.post("/number_pool", response_model=Dict[str, Any])
def number_pool(body: NumberPoolRequestBody, request: Request) -> Dict[str, Any]:
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)

    zar = body["properties"].get("zar", {}) or {}
    vid, sid, cid = get_zar_ids(zar)
    if not sid:
        warn(f"No SID")
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NO_SID,
        )

    pool_id = body["pool_id"]
    number = body["number"] or None
    context = body["context"] or {}
    request_context = dict(
        sid=sid,
        sid_original_referer=zar["sid"].get("origReferrer", None),
        ip=headers["ip"],
        user_agent=headers["user_agent"],
        referer=headers["referer"],
        host=headers["host"],
        visits={vid: context},
    )

    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )

    try:
        res = pool_api.lease_number(
            pool_id,
            request_context,
            target_number=number,
            renew=True if number else False,
        )
    except NumberPoolEmpty as e:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.EMPTY,
        )
    except NumberNotFound as e:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NOT_FOUND,
        )
    except NumberMaxRenewalExceeded as e:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.MAX_RENEWAL,
        )

    return dict(status=NumberPoolResponseStatus.SUCCESS, number=res, msg=None)


@router.post("/track_call", response_model=Dict[str, Any])
def track_call(body: TrackCallRequestBody, request: Request) -> Dict[str, Any]:
    body = dict(body)
    key = body.get("key", None)
    if (not settings.DEBUG) and ((not key) or (key != settings.NUMBER_POOL_KEY)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if settings.DEBUG:
        print_request(request.headers, body)

    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )

    ctx = pool_api.get_number_context(body["call_to"].lstrip("+1"))
    if not ctx:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.NOT_FOUND,
        )

    ctx_json = json.dumps(ctx)
    insert_stmt = insert(models.TrackCall).values(
        call_id=body["call_id"],
        call_from=body["call_from"],
        call_to=body["call_to"],
        number_context=ctx_json,
    )

    try:
        engine.execute(insert_stmt)
    except Exception as e:
        error("Failed to save TrackCall record:" + str(e))
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.INTERNAL_ERROR,
        )

    return dict(status=NumberPoolResponseStatus.SUCCESS, msg=ctx_json)


@router.get("/refresh_number_pool_conn", response_model=Dict[str, Any])
def refresh_number_pool_conn(request: Request, key: str = None) -> Dict[str, Any]:
    if (not settings.DEBUG) and ((not key) or (key != settings.NUMBER_POOL_KEY)):
        raise HTTPException(status_code=403, detail="Forbidden")
    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )
    pool_api.refresh_conn()
    return dict(status=NumberPoolResponseStatus.SUCCESS, msg=None)


@router.get("/init_number_pools", response_model=Dict[str, Any])
def init_number_pools(request: Request, key: str = None) -> Dict[str, Any]:
    if (not settings.DEBUG) and ((not key) or (key != settings.NUMBER_POOL_KEY)):
        raise HTTPException(status_code=403, detail="Forbidden")
    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )
    res = pool_api.init_pools()
    return dict(status=NumberPoolResponseStatus.SUCCESS, msg=json.dumps(res))


@router.get("/reset_pool", response_model=Dict[str, Any])
def reset_pool(
    request: Request, pool_id: int, preserve: bool = True, key: str = None
) -> Dict[str, Any]:
    if (not settings.DEBUG) and ((not key) or (key != settings.NUMBER_POOL_KEY)):
        raise HTTPException(status_code=403, detail="Forbidden")
    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )
    pool_api._reset_pool(pool_id, preserve=preserve)
    return dict(status=NumberPoolResponseStatus.SUCCESS, msg=None)


@router.get("/number_pool_stats", response_model=Dict[str, Any])
def number_pool_stats(
    request: Request, key: str = None, with_contexts: bool = False
) -> Dict[str, Any]:
    if (not settings.DEBUG) and ((not key) or (key != settings.NUMBER_POOL_KEY)):
        raise HTTPException(status_code=403, detail="Forbidden")
    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )
    return pool_api.get_all_pool_stats(with_contexts=with_contexts)


@router.get("/ok")
def ok(request: Request) -> str:
    return "OK"
