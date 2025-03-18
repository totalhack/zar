import random
import time
from urllib.parse import parse_qs, urlparse, quote, unquote
import uuid

from tlbx import pp, st, json, raiseifnot

from app.core.config import settings
from app.core.logging import dbg, info, warn, error


if settings.ROLLBAR_ENABLED:
    print("Initializing Rollbar")
    import rollbar


def rb_msg(msg, level, request=None, extra_data=None):
    if settings.ROLLBAR_ENABLED:
        if not isinstance(msg, str):
            try:
                msg = json.dumps(msg)
            except:
                pass
        rollbar.report_message(msg, level, request=request, extra_data=extra_data)


def rb_warning(msg, request=None, extra_data=None):
    warn(msg)
    rb_msg(msg, "warning", request=request, extra_data=extra_data)


def rb_error(msg, request=None, extra_data=None):
    error(msg)
    rb_msg(msg, "error", request=request, extra_data=extra_data)


def print_request(headers, body):
    print("---- Headers")
    pp(headers)
    print("---- Body")
    pp(body)


def extract_header_params(headers):
    host = headers.get("x-forwarded-host", None) or headers.get("host", None)
    origin = headers.get("origin", None)
    ip = (
        headers.get("x-forwarded-for", None)
        or headers.get("x-real-ip", None)
        or headers.get("forwarded", None)
    )
    user_agent = headers.get("user-agent", None)
    referer = headers.get("referer", None)
    return dict(host=host, origin=origin, ip=ip, user_agent=user_agent, referer=referer)


TO_BASE_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"


def to_base(s, b):
    res = ""
    while s:
        res += TO_BASE_CHARS[s % b]
        s //= b
    return res[::-1] or "0"


def create_vid():
    # Mimics this JS logic:
    #   vid = Date.now().toString(36) + '.' + Math.random().toString(36).substring(2);
    return (
        to_base(int(time.time_ns() // 1e6), 36)
        + "."
        + to_base(int(str(random.random())[2:]), 36)
    )


def create_zar_id():
    return str(uuid.uuid4())


def get_orig_referrer(headers):
    # If the front end passes one sourced from document.referrer we use it
    return (
        (headers or {}).get("document_referrer", "") or headers.get("referer", "") or ""
    )


def create_vid_dict(id=None, t=None, headers=None):
    origReferrer = get_orig_referrer(headers)
    t = t or int(time.time_ns() // 1e6)
    return dict(
        id=id or create_vid(),
        isNew=True,
        visits=1,
        origReferrer=origReferrer,
        t=t,
    )


def create_id_dict(id=None, t=None, headers=None, reset_param_value=None):
    origReferrer = get_orig_referrer(headers)
    t = t or int(time.time_ns() // 1e6)
    return dict(
        id=id or create_zar_id(),
        isNew=True,
        visits=1,
        origReferrer=origReferrer,
        t=t,
        resetParamValue=reset_param_value,
    )


def create_zar_dict():
    """Server-side ID generation logic ~matches client side. Currently used for noscript"""
    t = int(time.time_ns() // 1e6)
    return dict(
        cid=create_id_dict(t=t),
        sid=create_id_dict(t=t),
        vid=create_vid_dict(t=t),
    )


def get_zar_ids(zar):
    vid = zar.get("vid", {}).get("id", None) or None
    sid = zar.get("sid", {}).get("id", None) or None
    cid = zar.get("cid", {}).get("id", None) or None
    return vid, sid, cid


def handle_zar_id_cookie(
    zar,
    cookie,
    key,
    headers,
    t=None,
    reset_param_value=None,
    new_visit=False,
):
    raiseifnot(cookie, f"Expected cookie value, got: {cookie}")

    # We moved to JSON format, but need to handle old case too
    if cookie.startswith("{"):
        zar[key] = json.loads(cookie)
        if "visits" in zar[key]:
            zar[key]["isNew"] = False
            if new_visit:
                zar[key]["visits"] += 1

        if reset_param_value and reset_param_value != zar[key].get(
            "resetParamValue", None
        ):
            # Force a reset and clear out stale info
            old_id = zar[key]["id"]
            zar[key] = create_id_dict(
                t=t, headers=headers, reset_param_value=reset_param_value
            )
            new_id = zar[key]["id"]
            zar["session_reset"] = True
            warn(f"Reset session for {old_id} -> {new_id}")
    else:
        # Assume old style - cookie was just an ID, convert to dict
        zar[key] = create_id_dict(
            id=cookie, t=t, headers=headers, reset_param_value=reset_param_value
        )
    return zar


def get_zar_dict(zar, headers, sid_cookie=None, cid_cookie=None, create=True, url=None):
    zar = zar or {}
    t = int(time.time_ns() // 1e6)

    if create and "vid" not in zar:
        zar["vid"] = create_vid_dict(t=t, headers=headers)

    new_visit = False
    if zar["vid"].get("isNew", True):
        new_visit = True

    reset_param_value = None
    if settings.SESSION_RESET_PARAM and url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        reset_param_value = qs.get(settings.SESSION_RESET_PARAM, None)
        reset_param_value = reset_param_value[0] if reset_param_value else None

    zar["session_reset"] = False
    if sid_cookie:
        handle_zar_id_cookie(
            zar,
            sid_cookie,
            "sid",
            headers,
            t=t,
            reset_param_value=reset_param_value,
            new_visit=new_visit,
        )
    elif create and "sid" not in zar:
        zar["sid"] = create_id_dict(
            t=t, headers=headers, reset_param_value=reset_param_value
        )

    if cid_cookie:
        handle_zar_id_cookie(zar, cid_cookie, "cid", headers, t=t, new_visit=new_visit)
    elif create and "cid" not in zar:
        zar["cid"] = create_id_dict(t=t, headers=headers)

    return zar


def unquote_cookies(*args):
    return [unquote(cookie) if cookie else None for cookie in args]


def zar_cookie_params(key, value, headers, **kwargs):
    # https://www.starlette.io/responses/#set-cookie

    domain = None
    raw_domain = None
    if headers["origin"]:
        raw_domain = urlparse(headers["origin"]).netloc
    elif headers["host"]:
        raw_domain = headers["host"]

    if raw_domain:
        domain = ".".join(raw_domain.split(":")[0].split(".")[-2:])

    params = dict(
        key=key,
        value=quote(value),  # URL Encode
        samesite="none",
        httponly=True,
        secure=True if domain != "testserver" else False,
        path="/",
        domain=domain if domain != "testserver" else None,
    )
    params.update(kwargs)
    if params["max_age"]:
        params["expires"] = params["max_age"]
    return params
