import random
import time
import uuid

from tlbx import pp, info


def print_request(headers, body):
    print("---- Headers")
    pp(headers)
    print("---- Body")
    pp(body)


def extract_header_params(headers):
    host = headers.get("x-forwarded-host", None) or headers.get("host", None)
    ip = (
        headers.get("x-forwarded-for", None)
        or headers.get("x-real-ip", None)
        or headers.get("forwarded", None)
    )
    user_agent = headers.get("user-agent", None)
    referer = headers.get("referer", None)
    return dict(host=host, ip=ip, user_agent=user_agent, referer=referer)


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


def create_sid():
    return str(uuid.uuid4())


def create_cid():
    return str(uuid.uuid4())


def create_zar_dict():
    """Server-side ID generation logic ~matches client side. Currently used for noscript"""
    t = int(time.time_ns() // 1e6)
    return dict(
        cid=dict(id=create_cid(), isNew=True, visits=1, origReferrer="", t=t),
        sid=dict(id=create_sid(), isNew=True, visits=1, origReferrer="", t=t),
        vid=dict(id=create_vid(), isNew=True, visits=1, origReferrer="", t=t),
    )


def get_zar_ids(zar, cookie_sid=None, cookie_cid=None):
    vid_dict = zar.get("vid", {})
    sid_dict = zar.get("sid", {})
    cid_dict = zar.get("cid", {})
    vid = vid_dict.get("id", None) if vid_dict else None
    sid = sid_dict.get("id", None) if sid_dict else None
    cid = cid_dict.get("id", None) if cid_dict else None
    if cookie_sid and cookie_sid != sid:
        info(f"Overwriting SID {sid} with cookie_sid {cookie_sid}")
        sid = cookie_sid
        sid_dict["id"] = sid
        sid_dict["cookie_mismatch"] = True
    if cookie_cid and cookie_cid != cid:
        info(f"Overwriting CID {cid} with cookie_cid {cookie_cid}")
        cid = cookie_cid
        cid_dict["id"] = cid
        cid_dict["cookie_mismatch"] = True
    return vid, sid, cid