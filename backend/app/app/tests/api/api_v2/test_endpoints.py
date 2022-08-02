import time

from fastapi.testclient import TestClient
from tlbx import st, pp

from app.core.config import settings
from app.number_pool import NumberPoolResponseStatus


SAMPLE_PAGE_REQUEST = {
    "type": "page",
    "properties": {
        "title": "Page One",
        "url": "http://localhost:8080/one",
        "pool_id": None,
        "width": 1680,
        "height": 619,
        "referrer": "http://localhost:8080/one",
        "zar": {
            "vid": {
                "id": "kgwevbe3.ryqmjkraheq",
                "t": 1604071692651,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
        },
    },
    "options": {},
    "userId": None,
    "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbf",
    "meta": {"timestamp": 1604071694775},
}


def page(client, req=SAMPLE_PAGE_REQUEST):
    resp = client.post(f"{settings.API_V1_STR}/page", json=req)
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("id", None)
    cookies = resp.cookies.get_dict()
    assert "_zar_sid" in cookies
    return resp, data


def page_with_pool(client, pool_id=1, max_age=None):
    req = SAMPLE_PAGE_REQUEST.copy()
    req["properties"]["pool_id"] = pool_id
    if max_age:
        req["properties"]["pool_max_age"] = max_age
    req["properties"]["url"] = "http://localhost:8080/one?pl=1"
    resp, data = page(client, req=req)
    cookies = resp.cookies.get_dict()
    assert "_zar_pool" in cookies
    return resp, data


def test_endpoint_page(client: TestClient) -> None:
    page(client)


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
                "id": "kgwevbe3.ryqmjkraheq",
                "t": 1604071692651,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
        },
        "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbf",
        "category": "All",
    },
    "options": {},
    "userId": None,
    "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbf",
    "meta": {"timestamp": 1604072961820},
}


def test_endpoint_track(client: TestClient) -> None:
    resp = client.post(f"{settings.API_V1_STR}/track", json=SAMPLE_TRACK_REQUEST)
    assert resp.status_code == 200
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
                "id": "kgwevbe3.ryqmjkraheq",
                "t": 1604071692651,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
        },
        "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbf",
        "category": "All",
    },
    "options": {},
    "userId": None,
    "anonymousId": "29d7dfba-47ed-4305-ad91-e0625101afbf",
    "meta": {"timestamp": 1604072961820},
}


def test_endpoint_number_pool_init(client: TestClient) -> None:
    resp, data = page(client)  # without pool, just to set cookies
    resp = client.post(
        f"{settings.API_V1_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS


def test_endpoint_number_pool_no_sid(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_V1_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert (
        data["status"] == NumberPoolResponseStatus.ERROR
        and data["msg"] == "no session ID"
    )


def test_endpoint_number_session_expired(client: TestClient) -> None:
    MAX_AGE = 2
    resp, data = page_with_pool(client, max_age=MAX_AGE)
    assert data.get("pool_data", None) and data["pool_data"].get("number", None)

    print(f"Sleeping for {MAX_AGE + 1} seconds")
    time.sleep(MAX_AGE + 1)

    req = SAMPLE_NUMBER_POOL_REQUEST.copy()
    req["number"] = data["pool_data"]["number"]
    resp = client.post(f"{settings.API_V1_STR}/number_pool", json=req)
    assert resp.status_code == 200
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
    resp = client.post(
        f"{settings.API_V1_STR}/track_call", json=SAMPLE_TRACK_CALL_REQUEST
    )
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    # We didn't create a number context so this should respond with an error
    assert data.get("status", None) == NumberPoolResponseStatus.ERROR


def test_endpoint_call_track_success(client: TestClient) -> None:
    resp = client.get(
        f"{settings.API_V1_STR}/reset_pool",
        params=dict(key="abc", pool_id=1, preserve=False),
    )
    assert resp.status_code == 200

    resp, data = page(client)  # without pool, just to set cookies
    resp = client.post(
        f"{settings.API_V1_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS
    number = data["number"]

    track_call_req = SAMPLE_TRACK_CALL_REQUEST.copy()
    track_call_req["call_to"] = number
    pp(track_call_req)

    resp = client.post(f"{settings.API_V1_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS

    # route context should come into play on this one
    resp = client.post(f"{settings.API_V1_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS
