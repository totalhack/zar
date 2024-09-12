"""
TODO Async db connections: https://github.com/encode/databases
TODO Check for bots before deps.get_conn
"""
import time
from typing import Generator, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import insert
from starlette.status import HTTP_204_NO_CONTENT
from tlbx import st, json, dbg, info, warn
from urllib.parse import urlparse, parse_qs

from app import models
from app.schemas.zar import (
    PageRequestBody,
    TrackRequestBody,
    TrackCallRequestBody,
    NumberPoolRequestBody,
    UpdateNumberRequestBody,
)
from app.api import deps
from app.core.config import settings
from app.number_pool import (
    NumberPoolAPI,
    NumberPoolResponseStatus,
    NumberPoolResponseMessages,
    NumberPoolUnavailable,
    NumberPoolEmpty,
    NumberNotFound,
    NumberMaxRenewalExceeded,
    SessionNumberUnavailable,
)
from app.utils import (
    print_request,
    extract_header_params,
    get_zar_dict,
    get_zar_ids,
    zar_cookie_params,
    unquote_cookies,
    rb_warning,
    rb_error,
)

DAYS = 24 * 60 * 60
CID_COOKIE_MAX_AGE = 2 * 365 * DAYS
CID_COOKIE_NAME = "_zar_cid"
SID_COOKIE_MAX_AGE = 7 * DAYS
SID_COOKIE_NAME = "_zar_sid"
# This should line up with the pool max renewal time
POOL_COOKIE_MAX_AGE = 7 * DAYS
POOL_COOKIE_NAME = "_zar_pool"

router = APIRouter()

# TODO add config to skip this
pool_api = None
if settings.NUMBER_POOL_ENABLED:
    try:
        pool_api = NumberPoolAPI()
    except NumberPoolUnavailable as e:
        warn(str(e))


def get_pool_context(vid, sid, sid_original_referer, context, headers):
    res = dict(
        sid=sid,
        sid_original_referer=sid_original_referer,
        ip=headers["ip"],
        user_agent=headers["user_agent"],
        referer=headers["referer"],
        host=headers["host"],
        latest_context=context,
        visits={vid: context},  # TODO need to confirm renewal ctx merge works
    )
    return res


def get_pool_number(pool_api, pool_id, context, number=None, request=None):
    if not pool_api:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            pool_id=None,
            number=None,
            msg=NumberPoolResponseMessages.POOL_UNAVAILABLE,
        )
        warn(res)
        return res

    try:
        res = pool_api.lease_number(
            pool_id,
            context,
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
        rb_error(f"NumberPoolEmpty: pool ID {pool_id}: {str(e)}", request=request)
    except SessionNumberUnavailable as e:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NUMBER_UNAVAILABLE,
        )
        rb_warning(
            f"SessionNumberUnavailable: pool ID {pool_id}: {str(e)}", request=request
        )
    except NumberNotFound as e:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NOT_FOUND,
        )
        rb_warning(f"NumberNotFound: pool ID {pool_id}: {str(e)}", request=request)
    except NumberMaxRenewalExceeded as e:
        res = dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.MAX_RENEWAL,
        )
    res["pool_id"] = pool_id
    return res


def set_pool_cookie(response, data, headers, max_age=POOL_COOKIE_MAX_AGE):
    dbg(f"Setting pool cookie: {data}")
    response.set_cookie(
        **zar_cookie_params(
            POOL_COOKIE_NAME,
            json.dumps(data),
            headers,
            max_age=max_age,
        )
    )


def handle_pool_request(zar, props, cookie, headers, request, response):
    start = time.time()
    use_pool = False
    pool_sesh = {}
    pool_id = props.get("pool_id", None)
    if not pool_id:
        dbg("No pool ID on request")
        return

    pool_id = int(pool_id)
    pool_context = props.get("pool_context", None) or {}

    if cookie:
        try:
            pool_sesh = json.loads(cookie)
            use_pool = pool_sesh["enabled"]
        except Exception as e:
            rb_warning(
                f"Could not parse pool cookie: {cookie}: {str(e)}", request=request
            )
    else:
        parsed = urlparse(props["url"])
        qs = parse_qs(parsed.query)
        pl = qs.get("pl", None)
        if pl and str(pl[0]) == "1":
            use_pool = True

    if not use_pool:
        dbg(f"pool_id={pool_id} use_pool=False")
        return None

    vid, sid, _ = get_zar_ids(zar)
    pool_number = None

    if pool_sesh and str(pool_id) in pool_sesh["numbers"]:
        sesh_result = pool_sesh["numbers"][str(pool_id)]
        if sesh_result["status"] != NumberPoolResponseStatus.SUCCESS:
            warn(f"Returning cached unsuccessful pool result: {sesh_result}")
            return sesh_result

        if sesh_result["number"]:
            pool_number = sesh_result["number"]

    request_context = get_pool_context(
        vid,
        sid,
        zar["sid"].get("origReferrer", None),
        pool_context,
        headers,
    )

    global pool_api
    pool_resp = get_pool_number(
        pool_api, pool_id, request_context, number=pool_number, request=request
    )
    info(f"{sid}: {pool_resp}")

    # NOTE: numeric pool IDs get coerced to str in json.dumps, so we need to
    # to read and write as str when dealing with the cookie value.
    if pool_sesh:
        pool_sesh.setdefault("numbers", {})[str(pool_id)] = pool_resp
    else:
        pool_sesh = dict(enabled=True, numbers={str(pool_id): pool_resp})

    max_age = props.get("pool_max_age", POOL_COOKIE_MAX_AGE)
    set_pool_cookie(response, pool_sesh, headers, max_age=max_age)

    info(f"took: {time.time() - start:0.3f}s")
    return pool_resp


@router.post("/page", response_model=Dict[str, Any])
def page(
    body: PageRequestBody,
    request: Request,
    response: Response,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    _zar_pool: Optional[str] = Cookie(None),
    conn: Generator = Depends(deps.get_conn),
) -> Dict[str, Any]:
    start = time.time()
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)
    _zar_sid, _zar_cid, _zar_pool = unquote_cookies(_zar_sid, _zar_cid, _zar_pool)

    body["properties"] = body["properties"] or {}
    if body["properties"].get("is_bot", False) and not settings.ALLOW_BOTS:
        info(f"skipping bot: {headers['user_agent']}")
        return {}

    if "referrer" in body["properties"]:
        headers["document_referrer"] = body["properties"]["referrer"]

    zar = body["properties"].get("zar", {}) or {}
    zar = get_zar_dict(zar, headers, sid_cookie=_zar_sid, cid_cookie=_zar_cid)
    vid, sid, cid = get_zar_ids(zar)

    pool_data = None
    try:
        pool_data = handle_pool_request(
            zar, body["properties"], _zar_pool, headers, request, response
        )
        body["properties"]["pool_data"] = pool_data
    except Exception as e:
        rb_error(f"handle_pool_request failed: {str(e)}", request=request)

    stmt = insert(models.Page).values(
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
    res = conn.execute(stmt)
    pk = res.inserted_primary_key[0] if res.inserted_primary_key else None

    response.set_cookie(
        **zar_cookie_params(
            SID_COOKIE_NAME,
            json.dumps(zar["sid"]),
            headers,
            max_age=SID_COOKIE_MAX_AGE,
        )
    )
    response.set_cookie(
        **zar_cookie_params(
            CID_COOKIE_NAME,
            json.dumps(zar["cid"]),
            headers,
            max_age=CID_COOKIE_MAX_AGE,
        )
    )
    dbg(f"took: {time.time() - start:0.3f}s")
    return dict(vid=vid, sid=sid, cid=cid, id=pk, pool_data=pool_data)


@router.post("/track", response_model=Dict[str, Any])
def track(
    request: Request,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    conn: Generator = Depends(deps.get_conn),
    body_data: dict = Depends(deps.get_body_data),
):
    start = time.time()
    text_response = False
    if "text/plain" in request.headers["content-type"]:
        text_response = True

    try:
        body = TrackRequestBody(**body_data)
    except ValidationError as e:
        warn(body_data)
        raise HTTPException(status_code=422, detail="TrackRequestBody: " + str(e))

    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)

    body["properties"] = body["properties"] or {}
    if body["properties"].get("is_bot", False) and not settings.ALLOW_BOTS:
        info(f"skipping bot: {headers['user_agent']}")
        return {}

    if "referrer" in body["properties"]:
        headers["document_referrer"] = body["properties"]["referrer"]

    _zar_sid, _zar_cid = unquote_cookies(_zar_sid, _zar_cid)
    zar = body["properties"].get("zar", {})
    zar = get_zar_dict(
        zar, headers, sid_cookie=_zar_sid, cid_cookie=_zar_cid, create=False
    )
    vid, sid, cid = get_zar_ids(zar)
    if "zar" in body["properties"]:
        # Can get this data from the page/visit info
        del body["properties"]["zar"]

    stmt = insert(models.Track).values(
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
    res = conn.execute(stmt)

    dbg(f"took: {time.time() - start:0.3f}s")
    if text_response:
        # Assume it was a beacon call
        return Response(status_code=HTTP_204_NO_CONTENT)

    pk = res.inserted_primary_key[0] if res.inserted_primary_key else None
    resp = dict(id=pk)
    return JSONResponse(content=resp)


@router.get("/noscript", response_model=Dict[str, Any])
def noscript(
    request: Request,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    conn: Generator = Depends(deps.get_conn),
) -> Dict[str, Any]:
    if settings.DEBUG:
        print_request(request.headers, None)
    headers = extract_header_params(request.headers)

    _zar_sid, _zar_cid = unquote_cookies(_zar_sid, _zar_cid)
    zar = get_zar_dict({}, headers, sid_cookie=_zar_sid, cid_cookie=_zar_cid)
    props = dict(
        noscript=True,
        url=str(request.url),
        zar=zar,
    )

    vid, sid, cid = get_zar_ids(zar)

    stmt = insert(models.Page).values(
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
    res = conn.execute(stmt)
    pk = res.inserted_primary_key[0] if res.inserted_primary_key else None
    return dict(id=pk)


@router.post("/number_pool", response_model=Dict[str, Any])
def number_pool(
    body: NumberPoolRequestBody,
    request: Request,
    response: Response,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    _zar_pool: Optional[str] = Cookie(None),
) -> Dict[str, Any]:
    start = time.time()
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)
    _zar_sid, _zar_cid, _zar_pool = unquote_cookies(_zar_sid, _zar_cid, _zar_pool)

    body["properties"] = body["properties"] or {}
    if body["properties"].get("is_bot", False) and not settings.ALLOW_BOTS:
        warn(f"skipping bot: {headers['user_agent']}")
        return {}

    renew = False
    if body["number"]:
        renew = True

    if renew and (not _zar_pool):
        # The cookie is set on the first call either in this endpoint or page().
        # If it's missing, it must have expired.
        warn(f"number session expired: {body['properties']}")
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.EXPIRED,
        )

    zar = body["properties"].get("zar", {}) or {}
    zar = get_zar_dict(
        zar, headers, sid_cookie=_zar_sid, cid_cookie=_zar_cid, create=False
    )
    vid, sid, _ = get_zar_ids(zar)

    if not sid:
        warn(f"No SID: zar:{zar} cookie:{_zar_sid}")
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NO_SID,
        )

    pool_id = body["pool_id"]
    number = body["number"] or None
    context = body["context"] or {}
    origRef = zar["sid"].get("origReferrer", None)
    request_context = get_pool_context(vid, sid, origRef, context, headers)

    global pool_api
    res = get_pool_number(
        pool_api, pool_id, request_context, number=number, request=request
    )

    if not renew:
        pool_sesh = dict(enabled=True, numbers={pool_id: res})
        max_age = body["properties"].get("pool_max_age", POOL_COOKIE_MAX_AGE)
        set_pool_cookie(response, pool_sesh, headers, max_age=max_age)

    info(f"took: {time.time() - start:0.3f}s, {res}")
    return res


@router.post("/update_number", response_model=Dict[str, Any])
def update_number(
    body: UpdateNumberRequestBody,
    request: Request,
    _zar_sid: Optional[str] = Cookie(None),
    _zar_cid: Optional[str] = Cookie(None),
    _zar_pool: Optional[str] = Cookie(None),
) -> Dict[str, Any]:
    start = time.time()
    body = dict(body)
    if settings.DEBUG:
        print_request(request.headers, body)
    headers = extract_header_params(request.headers)
    _zar_sid, _zar_cid, _zar_pool = unquote_cookies(_zar_sid, _zar_cid, _zar_pool)

    body["properties"] = body["properties"] or {}
    if body["properties"].get("is_bot", False) and not settings.ALLOW_BOTS:
        warn(f"skipping bot: {headers['user_agent']}")
        return {}

    zar = body["properties"].get("zar", {}) or {}
    zar = get_zar_dict(
        zar, headers, sid_cookie=_zar_sid, cid_cookie=_zar_cid, create=False
    )
    vid, sid, _ = get_zar_ids(zar)

    if not sid:
        warn(f"No SID: zar:{zar} cookie:{_zar_sid}")
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            number=None,
            msg=NumberPoolResponseMessages.NO_SID,
        )

    pool_id = body["pool_id"]
    number = body["number"]
    context = body["context"]
    origRef = zar["sid"].get("origReferrer", None)
    request_context = get_pool_context(vid, sid, origRef, context, headers)

    global pool_api
    res = pool_api.update_number(pool_id, number, request_context, merge=True)

    info(f"took: {time.time() - start:0.3f}s, {pool_id} / {number}")
    return dict(status=NumberPoolResponseStatus.SUCCESS, context=res, msg=None)


@router.post("/track_call", response_model=Dict[str, Any])
def track_call(
    body: TrackCallRequestBody,
    request: Request,
    conn: Generator = Depends(deps.get_conn),
) -> Dict[str, Any]:
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
            msg=NumberPoolResponseMessages.POOL_UNAVAILABLE,
        )
        rb_warning(res, request=request)
        return res

    call_to = body["call_to"].lstrip("+1")
    call_from = body["call_from"].lstrip("+1")
    number_ctx = pool_api.get_number_context(call_to)
    route_ctx = pool_api.get_cached_route_context(call_from, call_to)
    from_route_cache = False
    ctx = None

    if (not number_ctx) and route_ctx:
        # No active context found for this tracking number but we have a cached
        # context from this user calling this number before.
        ctx = route_ctx
        from_route_cache = True
    elif number_ctx and not route_ctx:
        ctx = number_ctx
    elif number_ctx and route_ctx:
        # There is an active context and a cached context. If the SID of number context
        # and route context match, its the same user and we use the updated context.
        pool_id = number_ctx["pool_id"]
        number_sid = pool_api._get_session_id(pool_id, number_ctx["request_context"])
        route_sid = pool_api._get_session_id(pool_id, route_ctx["request_context"])
        if number_sid == route_sid:
            # Same session, use direct number ctx since it may be more up to date
            ctx = number_ctx
        else:
            # Different session, so likely a different user has this number now. Use
            # the cached route context for this user.
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
        conn.execute(insert_stmt)
    except Exception as e:
        rb_error(f"Failed to save TrackCall record: {str(e)}", request=request)
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.INTERNAL_ERROR,
        )

    return dict(status=NumberPoolResponseStatus.SUCCESS, msg=ctx)


@router.get("/refresh_number_pool_conn", response_model=Dict[str, Any])
def refresh_number_pool_conn(request: Request, key: str = None) -> Dict[str, Any]:
    if (not settings.DEBUG) and ((not key) or (key != settings.NUMBER_POOL_KEY)):
        raise HTTPException(status_code=403, detail="Forbidden")
    global pool_api
    if not pool_api:
        return dict(
            status=NumberPoolResponseStatus.ERROR,
            msg=NumberPoolResponseMessages.POOL_UNAVAILABLE,
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
            msg=NumberPoolResponseMessages.POOL_UNAVAILABLE,
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
            msg=NumberPoolResponseMessages.POOL_UNAVAILABLE,
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
            msg=NumberPoolResponseMessages.POOL_UNAVAILABLE,
        )
    return pool_api.get_all_pool_stats(with_contexts=with_contexts)


@router.get("/ok")
def ok(request: Request) -> str:
    return "OK"
