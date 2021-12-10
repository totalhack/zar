from typing import Generator, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy import insert
from sqlalchemy.inspection import inspect
from tlbx import st, json, info, warn, error

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
from app.utils import (
    print_request,
    extract_header_params,
    create_zar_dict,
    get_zar_ids,
    zar_cookie_params,
)

DAYS = 24 * 60 * 60
CID_MAX_AGE = 2 * 365 * DAYS
CID_COOKIE_NAME = "_zar_cid"
SID_MAX_AGE = 7 * DAYS
SID_COOKIE_NAME = "_zar_sid"

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
    response: Response,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)

    body["properties"] = body["properties"] or {}
    zar = body["properties"].get("zar", {}) or {}
    vid, sid, cid = get_zar_ids(zar, cookie_sid=_zar_sid, cookie_cid=_zar_cid)

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

    id_dict = dict(vid=vid, sid=sid, cid=cid)
    response.set_cookie(**zar_cookie_params(SID_COOKIE_NAME, sid, max_age=SID_MAX_AGE))
    response.set_cookie(**zar_cookie_params(CID_COOKIE_NAME, cid, max_age=CID_MAX_AGE))

    id_dict["id"] = pk
    return id_dict


@router.post("/track", response_model=Dict[str, Any])
def track(
    body: TrackRequestBody,
    request: Request,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    db: Generator = Depends(deps.get_db),
) -> Dict[str, Any]:
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)

    body["properties"] = body["properties"] or {}
    zar = body["properties"].get("zar", {})
    vid, sid, cid = get_zar_ids(zar, cookie_sid=_zar_sid, cookie_cid=_zar_cid)
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
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
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

    vid, sid, cid = get_zar_ids(zar, cookie_sid=_zar_sid, cookie_cid=_zar_cid)
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
def number_pool(
    body: NumberPoolRequestBody,
    request: Request,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
) -> Dict[str, Any]:
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)

    zar = body["properties"].get("zar", {}) or {}
    vid, sid, cid = get_zar_ids(zar, cookie_sid=_zar_sid, cookie_cid=_zar_cid)
    if not sid:
        warn("No SID")
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
        visits={vid: context},  # TODO need to confirm renewal ctx merge works
    )

    global pool_api
    if not pool_api:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )
        warn(res)
        return res

    try:
        res = pool_api.lease_number(
            pool_id,
            request_context,
            target_number=number,
            renew=True if number else False,
        )
        res = dict(status=NumberPoolResponseStatus.SUCCESS, number=res, msg=None)
    except NumberPoolEmpty as e:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.EMPTY,
        )
    except NumberNotFound as e:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NOT_FOUND,
        )
    except NumberMaxRenewalExceeded as e:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.MAX_RENEWAL,
        )

    info(res)
    return res


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
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.UNAVAILABLE,
        )
        warn(res)
        return res

    call_to = body["call_to"].lstrip("+1")
    call_from = body["call_from"].lstrip("+1")
    number_ctx = pool_api.get_number_context(call_to)
    route_ctx = pool_api.get_cached_route_context(call_from, call_to)
    from_route_cache = False
    ctx = None

    if (not number_ctx) and route_ctx:
        ctx = route_ctx
        from_route_cache = True
    elif number_ctx and not route_ctx:
        ctx = number_ctx
    elif number_ctx and route_ctx:
        pool_id = number_ctx["pool_id"]
        number_sid = pool_api._get_session_id(pool_id, number_ctx["request_context"])
        route_sid = pool_api._get_session_id(pool_id, route_ctx["request_context"])
        if number_sid == route_sid:
            # Same session, use direct number ctx since it may be more up to date
            ctx = number_ctx
        else:
            # Different session, so likely a different user has this number now. Use
            # the cached route context.
            ctx = route_ctx
            from_route_cache = True

    if not ctx:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.NOT_FOUND,
        )
        warn(f"{call_from} -> {call_to}: {res}")
        return res

    pool_api.set_cached_route_context(call_from, call_to, ctx)

    ctx_json = json.dumps(ctx)
    insert_stmt = insert(models.TrackCall).values(
        call_id=body["call_id"],
        sid=ctx.get("request_context", {}).get("sid", None),
        call_from=call_from,
        call_to=call_to,
        number_context=ctx_json,
        from_route_cache=from_route_cache,
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
