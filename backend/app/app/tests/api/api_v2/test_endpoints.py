import copy
import json
import time
from urllib.parse import quote

from fastapi.testclient import TestClient
from tlbx import st, pp

from app.api.api_v2.endpoints import zar as zar_endpoints
from app.core.config import settings
from app.number_pool import NumberPoolResponseStatus


AREA_CODE_POOL_ID = 3

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


def test_options_request_page(client: TestClient) -> None:
    resp = client.options(
        f"{settings.API_V2_STR}/page",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200, resp.text
    assert "access-control-allow-methods" in resp.headers, resp.headers
    allowed_methods = resp.headers["access-control-allow-methods"]
    assert "POST" in allowed_methods
    assert "OPTIONS" in allowed_methods


def page_with_pool(client, pool_id=1, max_age=None, url=None):
    req = SAMPLE_PAGE_REQUEST.copy()
    req["properties"]["pool_id"] = pool_id
    if max_age:
        req["properties"]["pool_max_age"] = max_age
    url = url or "http://localhost:8080/one?pl=1"
    req["properties"]["url"] = url
    # It's necessary to also put certain context items in here if you want
    # it to be accessible to all pool functionality such as assessing
    # the area code.
    req["properties"]["pool_context"] = dict(url=url)
    resp, data = page(client, req=req)
    cookies = dict(resp.cookies)
    assert "_zar_pool" in cookies
    return resp, data


def reset_pool(client, pool_id=1):
    resp = client.get(
        f"{settings.API_V2_STR}/reset_pool",
        params=dict(key="abc", pool_id=pool_id, preserve=False),
    )
    assert resp.status_code == 200, resp.text


def remove_user_context(client, id_type, user_id):
    resp = client.get(
        f"{settings.API_V2_STR}/remove_user_context",
        params=dict(key="abc", user_id=user_id, id_type=id_type),
    )
    assert resp.status_code == 200, resp.text


def clear_cached_route_context(call_from, call_to):
    if not zar_endpoints.pool_api:
        return
    key = zar_endpoints.pool_api.get_cached_route_key(call_from, call_to)
    zar_endpoints.pool_api.conn.delete(key)


def clear_sid_user_context(user_id):
    if not zar_endpoints.pool_api:
        return
    zar_endpoints.pool_api.remove_user_context("sid", user_id)


def clear_sid_pool_number_mapping(pool_id, sid):
    if not zar_endpoints.pool_api:
        return
    key = zar_endpoints.pool_api._get_session_number_hash_name(pool_id)
    zar_endpoints.pool_api.conn.hdel(key, sid)


def test_endpoint_page_v2(client: TestClient):
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


# def test_endpoint_page_v2_performance(client: TestClient) -> None:
#     request_count = 1000
#     settings.DEBUG = False

#     import logging

#     logging.getLogger("databases").setLevel(logging.WARNING)
#     logging.getLogger("databases:mysql").setLevel(logging.WARNING)

#     req = copy.deepcopy(SAMPLE_PAGE_REQUEST)
#     req["properties"]["url"] = "http://localhost:8080/perf?s=1"

#     start = time.perf_counter()
#     for _ in range(request_count):
#         resp = client.post(f"{settings.API_V2_STR}/page", json=req)
#         assert resp.status_code == 200, resp.text

#     total_seconds = time.perf_counter() - start
#     requests_per_second = request_count / total_seconds if total_seconds else 0.0
#     pp(
#         {
#             "request_count": request_count,
#             "total_seconds": total_seconds,
#             "requests_per_second": requests_per_second,
#         }
#     )
#     settings.DEBUG = True


def test_endpoint_number_via_page(client: TestClient):
    resp, data = page_with_pool(client)
    assert data.get("pool_data", None) and data["pool_data"].get("number", None)


def test_endpoint_area_code_number_via_page(client: TestClient):
    pool_id = AREA_CODE_POOL_ID
    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test 9002212 (Pawtucket, RI), should get a 401 number
    url = "http://localhost:8080/one?pl=1&loc_interest_ms=&loc_physical_ms=9002212"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("401")
    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test 9002212 in loc_interest
    url = "http://localhost:8080/one?pl=1&loc_interest_ms=9002212"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("401")
    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test 9002212 in loc_physical with 1012873 (Anchorage, AK) as interest
    url = (
        "http://localhost:8080/one?pl=1&loc_physical_ms=9002212&loc_interest_ms=1012873"
    )
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("401")
    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test 1018455 (Wayland, MA), should get a 339 number
    url = "http://localhost:8080/one?pl=1&loc_interest_ms=&loc_physical_ms=1018455"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("339")

    client.cookies.clear()

    # Test 1018455 (Wayland, MA) again, should get a 781 number since 339 was taken but
    # Wayland also maps to 781 as an option.
    url = "http://localhost:8080/one?pl=1&loc_interest_ms=&loc_physical_ms=1018455"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("781")

    # Test invalid ID
    url = "http://localhost:8080/one?pl=1&loc_physical_ms=XYZ"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number

    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test valid but no area code match
    url = "http://localhost:8080/one?pl=1&loc_physical_ms=1012873"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number

    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test bing prefix 63978 (Pawtucket, RI), should get a 401 number
    url = "http://localhost:8080/one?s=bing&pl=1&loc_physical_ms=63978"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("401")

    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Test bing again with second bin ID
    url = "http://localhost:8080/one?s=bing2&pl=1&loc_physical_ms=63978"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("401")

    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Set geo_mode to 2, always use physical
    # Use 9002212 in loc_physical with 1018455 (Wayland, MA) as interest
    url = "http://localhost:8080/one?pl=1&loc_physical_ms=9002212&loc_interest_ms=1018455&gm=2"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("401")

    reset_pool(client, pool_id=pool_id)
    client.cookies.clear()

    # Set geo_mode to 3, always use interest
    # Use 9002212 in loc_physical with 1018455 (Wayland, MA) as interest
    url = "http://localhost:8080/one?pl=1&loc_physical_ms=9002212&loc_interest_ms=1018455&gm=3"
    resp, data = page_with_pool(client, pool_id=pool_id, url=url)
    number = data.get("pool_data", None) and data["pool_data"].get("number", None)
    print(number)
    assert number and number.startswith("339")


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


class FailOnEnterConnection:
    async def __aenter__(self):
        raise AssertionError("database connection should not be opened")

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_endpoint_page_bot_skips_db_connection(client: TestClient, monkeypatch) -> None:
    req = copy.deepcopy(SAMPLE_PAGE_REQUEST)
    req["properties"]["is_bot"] = True
    monkeypatch.setattr(
        zar_endpoints.database, "connection", lambda: FailOnEnterConnection()
    )

    resp = client.post(f"{settings.API_V2_STR}/page", json=req)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {}


def test_endpoint_track_bot_skips_db_connection(
    client: TestClient, monkeypatch
) -> None:
    req = copy.deepcopy(SAMPLE_TRACK_REQUEST)
    req["properties"]["is_bot"] = True
    monkeypatch.setattr(
        zar_endpoints.database, "connection", lambda: FailOnEnterConnection()
    )

    resp = client.post(f"{settings.API_V2_STR}/track", json=req)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {}


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


def test_endpoint_number_pool_rerequest_taken_number_reuses_number_area_code(
    client: TestClient,
) -> None:
    reset_pool(client, pool_id=AREA_CODE_POOL_ID)
    client.cookies.clear()

    targeted_url = (
        "http://localhost:8080/one?pl=1&loc_interest_ms=&loc_physical_ms=9002212"
    )
    _, first_data = page_with_pool(client, pool_id=AREA_CODE_POOL_ID, url=targeted_url)
    leased_number = first_data["pool_data"]["number"]
    assert leased_number.startswith("401")

    client.cookies.clear()
    page(client)

    renew_req = copy.deepcopy(SAMPLE_NUMBER_POOL_REQUEST)
    renew_req["pool_id"] = AREA_CODE_POOL_ID
    renew_req["number"] = leased_number
    renew_req["context"] = {}

    resp = client.post(f"{settings.API_V2_STR}/number_pool", json=renew_req)
    assert resp.status_code == 200, resp.text
    renew_data = resp.json()
    pp(renew_data)

    assert renew_data.get("status", None) == NumberPoolResponseStatus.SUCCESS
    assert renew_data["number"] != leased_number
    assert renew_data["number"].startswith("401")


def test_endpoint_page_uses_sid_cached_targeting_without_params(
    client: TestClient,
) -> None:
    reset_pool(client, pool_id=AREA_CODE_POOL_ID)
    client.cookies.clear()

    targeted_url = (
        "http://localhost:8080/one?pl=1&loc_interest_ms=&loc_physical_ms=9002212"
    )
    first_resp, first_data = page_with_pool(
        client, pool_id=AREA_CODE_POOL_ID, url=targeted_url
    )
    first_number = first_data["pool_data"]["number"]
    sid = first_data["sid"]
    sid_ctx = first_data["pool_data"].get("sid_ctx", {})
    targeting = sid_ctx.get("pool_targeting", {}).get(str(AREA_CODE_POOL_ID), {})

    assert first_number.startswith("401")
    assert set(targeting.keys()) == {"area_codes", "source", "updated_at"}
    assert targeting["area_codes"] == ["401"]
    assert targeting["source"] == "criteria"
    assert targeting["updated_at"]

    sid_cookie = first_resp.cookies.get("_zar_sid")
    assert sid_cookie

    clear_sid_pool_number_mapping(AREA_CODE_POOL_ID, sid)

    client.cookies.clear()
    client.cookies.set("_zar_sid", sid_cookie)

    revisit_resp, revisit_data = page_with_pool(
        client, pool_id=AREA_CODE_POOL_ID, url="http://localhost:8080/one?pl=1"
    )
    second_number = revisit_data["pool_data"]["number"]
    second_sid_ctx = revisit_data["pool_data"].get("sid_ctx", {})
    second_targeting = second_sid_ctx.get("pool_targeting", {}).get(
        str(AREA_CODE_POOL_ID), {}
    )

    assert revisit_resp.status_code == 200
    assert revisit_data["sid"] == sid
    assert second_number != first_number
    assert second_number.startswith("401")
    assert set(second_targeting.keys()) == {"area_codes", "source", "updated_at"}
    assert second_targeting["area_codes"] == ["401"]
    assert second_targeting["source"] == "criteria"
    assert second_targeting["updated_at"]


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


def test_endpoint_number_pool_handles_pool_unavailable(
    client: TestClient, monkeypatch
) -> None:
    page(client)
    monkeypatch.setattr(zar_endpoints, "pool_api", None)

    resp = client.post(
        f"{settings.API_V2_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)

    assert data["status"] == NumberPoolResponseStatus.ERROR
    assert data["msg"] == "pool unavailable"


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


def test_endpoint_page_ignores_cached_pool_error(client: TestClient) -> None:
    reset_pool(client)

    client.cookies.set(
        "_zar_pool",
        quote(
            json.dumps(
                {
                    "enabled": True,
                    "numbers": {
                        "1": {
                            "status": NumberPoolResponseStatus.ERROR,
                            "pool_id": 1,
                            "number": None,
                            "msg": "pool unavailable",
                        }
                    },
                }
            )
        ),
    )

    resp, data = page_with_pool(client, pool_id=1)
    assert data.get("pool_data", None)
    assert data["pool_data"]["status"] == NumberPoolResponseStatus.SUCCESS
    assert data["pool_data"].get("number", None)


SAMPLE_TRACK_CALL_REQUEST = {
    "key": "abc",
    "call_id": "1234",
    "call_from": "4011235555",
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

    new_req = copy.deepcopy(SAMPLE_NUMBER_POOL_REQUEST)
    # Add example location to request/pool context
    new_req["context"]["location"] = {
        "Name": "32256",
        "Parent ID": "21142",
        "Target Type": "Postal Code",
        "State": "Florida",
        "State Abbr": "FL",
        "Best Zip": "32256",
        "City": "Jacksonville",
        "Display Name": "Jacksonville, FL",
    }
    new_req["number"] = number
    resp = client.post(f"{settings.API_V2_STR}/update_number", json=new_req)
    data = resp.json()

    # Add user context which includes a zip
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
    assert data["msg"]["user_context"].get("zip_to_area_code_distance", None)
    assert data["msg"]["request_context"]["latest_context"].get(
        "zip_to_area_code_distance", None
    )

    # route context should come into play on this one
    resp = client.post(f"{settings.API_V2_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS

    remove_user_context(
        client, id_type="phone", user_id=SAMPLE_TRACK_CALL_REQUEST["call_from"]
    )


SAMPLE_USER_CONTEXT_REQUEST = {
    "key": "abc",
    "user_id": "4015735878",
    "id_type": "phone",
    "context": {"foo": "bar", "baz": "bar", "Zip": "02184"},
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


def test_endpoint_number_pool_renew_returns_sid_ctx(client: TestClient) -> None:
    """Test that renewing a number returns sid_ctx after track_call."""
    reset_pool(client)

    # Step 1: Lease a number via page with pool
    resp, data = page_with_pool(client)
    assert data.get("pool_data", None) and data["pool_data"].get("number", None)
    number = data["pool_data"]["number"]
    sid = data["sid"]

    # Clear any stale route or sid context from earlier tests so this verifies
    # the current session's track_call -> renewal path.
    clear_cached_route_context(SAMPLE_TRACK_CALL_REQUEST["call_from"], number)
    clear_sid_user_context(sid)

    # Step 2: Call track_call with the leased number
    track_call_req = SAMPLE_TRACK_CALL_REQUEST.copy()
    track_call_req["call_to"] = number
    resp = client.post(f"{settings.API_V2_STR}/track_call", json=track_call_req)
    assert resp.status_code == 200, resp.text
    track_data = resp.json()
    pp(track_data)
    assert track_data.get("status", None) == NumberPoolResponseStatus.SUCCESS

    # Step 3: Renew the number via number_pool endpoint
    renew_req = copy.deepcopy(SAMPLE_NUMBER_POOL_REQUEST)
    renew_req["number"] = number
    resp = client.post(f"{settings.API_V2_STR}/number_pool", json=renew_req)
    assert resp.status_code == 200, resp.text
    renew_data = resp.json()
    pp(renew_data)

    # Step 4: Confirm sid_ctx is returned
    assert renew_data.get("status", None) == NumberPoolResponseStatus.SUCCESS
    assert "sid_ctx" in renew_data, "sid_ctx should be present in renewal response"
    assert renew_data["sid_ctx"].get("last_called_number") == number
    assert renew_data["sid_ctx"].get("last_called_time") is not None
