import copy
import time

from fastapi.testclient import TestClient
from tlbx import st, pp

from app.core.config import settings
from app.number_pool import NumberPoolResponseStatus


SAMPLE_PAGE_REQUEST = {
    "type": "page",
    "properties": {
        "title": "Page One",
        "url": "http://localhost:8080/one?s=1",
        "pool_id": None,
        "width": 1680,
        "height": 619,
        "referrer": "http://example.com",
        "zar": {
            "vid": {
                "id": "kgwevbe3.ryqmjkrahew",
                "t": 1604071692651,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
        },
    },
    "options": {},
    "userId": None,
    "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbg",
    "meta": {"timestamp": 1604071694775},
}


def page(client, req=SAMPLE_PAGE_REQUEST):
    resp = client.post(f"{settings.API_V2_STR}/page", json=req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("id", None)
    cookies = dict(resp.cookies)
    assert "_zar_sid" in cookies
    return resp, data


def page_with_pool(client, pool_id=1, max_age=None):
    req = SAMPLE_PAGE_REQUEST.copy()
    req["properties"]["pool_id"] = pool_id
    if max_age:
        req["properties"]["pool_max_age"] = max_age
    req["properties"]["url"] = "http://localhost:8080/one?pl=1"
    resp, data = page(client, req=req)
    cookies = dict(resp.cookies)
    assert "_zar_pool" in cookies
    return resp, data


def reset_pool(client):
    resp = client.get(
        f"{settings.API_V2_STR}/reset_pool",
        params=dict(key="abc", pool_id=1, preserve=False),
    )
    assert resp.status_code == 200, resp.text


def test_endpoint_page_v2(client: TestClient) -> None:
    resp, data = page(client)
    sid1 = data["sid"]

    resp, data = page(client)
    sid2 = data["sid"]
    assert sid1 == sid2

    req = SAMPLE_PAGE_REQUEST.copy()
    # URL with new s= param should trigger a new session
    req["properties"]["url"] = "http://localhost:8080/one?s=2"
    resp, data = page(client, req=req)
    sid3 = data["sid"]
    assert sid1 != sid3

    # Same s= value, should not trigger a new session
    resp, data = page(client, req=req)
    sid4 = data["sid"]
    assert sid3 == sid4

    # URL with no s= param, should not trigger a new session
    req["properties"]["url"] = "http://localhost:8080/other"
    resp, data = page(client, req=req)
    sid5 = data["sid"]
    assert sid5 == sid4


def test_endpoint_number_via_page(client: TestClient) -> None:
    resp, data = page_with_pool(client)
    assert data.get("pool_data", None) and data["pool_data"].get("number", None)


SAMPLE_TRACK_REQUEST = {
    "type": "track",
    "event": "event1",
    "properties": {
        "attr1": "val1",
        "attr2": "val2",
        "url": "http://localhost:8080/one",
        "referrer": "http://localhost:8080/one",
        "zar": {
            "vid": {
                "id": "kgwevbe3.ryqmjkrahew",
                "t": 1604071692651,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
        },
        "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbg",
        "category": "All",
    },
    "options": {},
    "userId": None,
    "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbg",
    "meta": {"timestamp": 1604072961820},
}


def test_endpoint_track_v2(client: TestClient) -> None:
    resp = client.post(f"{settings.API_V2_STR}/track", json=SAMPLE_TRACK_REQUEST)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("id", None)


SAMPLE_NUMBER_POOL_REQUEST = {
    "pool_id": 1,
    "number": None,
    "context": {"foo": "bar", "baz": "bar"},
    "properties": {
        "attr1": "val1",
        "attr2": "val2",
        "zar": {
            "vid": {
                "id": "kgwevbe3.ryqmjkrahew",
                "t": 1604071692651,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
        },
        "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbg",
        "category": "All",
    },
    "options": {},
    "userId": None,
    "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbg",
    "meta": {"timestamp": 1604072961820},
}


def test_endpoint_init_number_pools(client: TestClient) -> None:
    resp = client.get(
        f"{settings.API_V2_STR}/init_number_pools", params=dict(pool_id=1)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS

    resp = client.get(f"{settings.API_V2_STR}/init_number_pools")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS


def test_endpoint_number_pool_init(client: TestClient) -> None:
    resp, data = page(client)  # without pool, just to set cookies
    resp = client.post(
        f"{settings.API_V2_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS


def test_endpoint_number_pool_no_sid(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_V2_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert (
        data["status"] == NumberPoolResponseStatus.ERROR
        and data["msg"] == "no session ID"
    )


def test_endpoint_number_pool_update(client: TestClient) -> None:
    resp, data = page(client)  # without pool, just to set cookies
    resp = client.post(
        f"{settings.API_V2_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS

    new_req = copy.deepcopy(SAMPLE_NUMBER_POOL_REQUEST)
    new_req["context"]["foo"] = "update"  # Put a new value in the context
    new_req["number"] = data["number"]
    resp = client.post(f"{settings.API_V2_STR}/update_number", json=new_req)
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS
    vid = new_req["properties"]["zar"]["vid"]["id"]
    assert data["context"]["request_context"]["visits"][vid]["foo"] == "update"


def test_endpoint_number_session_expired(client: TestClient) -> None:
    reset_pool(client)

    MAX_AGE = 2
    resp, data = page_with_pool(client, max_age=MAX_AGE)
    assert data.get("pool_data", None) and data["pool_data"].get("number", None)

    print(f"Sleeping for {MAX_AGE + 1} seconds")
    time.sleep(MAX_AGE + 1)

    req = SAMPLE_NUMBER_POOL_REQUEST.copy()
    req["number"] = data["pool_data"]["number"]
    resp = client.post(f"{settings.API_V2_STR}/number_pool", json=req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data["status"] == NumberPoolResponseStatus.ERROR and data["msg"] == "expired"


SAMPLE_TRACK_CALL_REQUEST = {
    "key": "abc",
    "call_id": "1234",
    "call_from": "5551235555",
    "call_to": "5551235556",
}


def test_endpoint_call_track_error(client: TestClient) -> None:
    ctx = SAMPLE_TRACK_CALL_REQUEST.copy()
    ctx["call_to"] = "1234567890"
    resp = client.post(f"{settings.API_V2_STR}/track_call", json=ctx)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    # We didn't create a number context so this should respond with an error
    assert data.get("status", None) == NumberPoolResponseStatus.ERROR


def test_endpoint_call_track_success(client: TestClient) -> None:
    reset_pool(client)

    resp, data = page(client)  # without pool, just to set cookies
    resp = client.post(
        f"{settings.API_V2_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS
    number = data["number"]

    # Add user context that should get returned later
    user_request = SAMPLE_USER_CONTEXT_REQUEST.copy()
    user_request["user_id"] = SAMPLE_TRACK_CALL_REQUEST["call_from"]
    resp = client.post(f"{settings.API_V2_STR}/update_user_context", json=user_request)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)

    track_call_req = SAMPLE_TRACK_CALL_REQUEST.copy()
    track_call_req["call_to"] = number
    pp(track_call_req)

    resp = client.post(f"{settings.API_V2_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS
    assert data.get("msg", {}).get("user_context", None)

    # route context should come into play on this one
    resp = client.post(f"{settings.API_V2_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS


SAMPLE_USER_CONTEXT_REQUEST = {
    "key": "abc",
    "user_id": "4015735878",
    "id_type": "phone",
    "context": {"foo": "bar", "baz": "bar"},
}


def test_endpoint_update_user_context(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_V2_STR}/update_user_context", json=SAMPLE_USER_CONTEXT_REQUEST
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)

    params = dict(
        key=SAMPLE_USER_CONTEXT_REQUEST["key"],
        user_id=SAMPLE_USER_CONTEXT_REQUEST["user_id"],
        id_type=SAMPLE_USER_CONTEXT_REQUEST["id_type"],
    )
    resp = client.get(f"{settings.API_V2_STR}/get_user_context", params=params)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)


SAMPLE_STATIC_NUMBER_CONTEXT_REQUEST = {
    "key": "abc",
    "contexts": [
        {
            "number": "5551237777",
            "context": {"test": "1"},
        }
    ],
}


def test_endpoint_set_static_number_contexts(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_V2_STR}/set_static_number_contexts",
        json=SAMPLE_STATIC_NUMBER_CONTEXT_REQUEST,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)

    first_number = SAMPLE_STATIC_NUMBER_CONTEXT_REQUEST["contexts"][0]["number"]
    params = dict(key=SAMPLE_USER_CONTEXT_REQUEST["key"], number=first_number)
    resp = client.get(f"{settings.API_V2_STR}/get_static_number_context", params=params)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)

    track_call_req = SAMPLE_TRACK_CALL_REQUEST.copy()
    track_call_req["call_to"] = first_number
    pp(track_call_req)

    resp = client.post(f"{settings.API_V2_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("msg", {}).get("static_context", None)
