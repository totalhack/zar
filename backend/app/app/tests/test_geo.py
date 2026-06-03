import copy
import json
import time
from types import SimpleNamespace

import geoip2.errors
import pytest
from tlbx import info

from app.api.api_v2.endpoints import zar as zar_endpoints
from app.core.config import settings
from app import geo as geo_module


LIVE_MAXMIND_TEST_IP = "68.9.28.187"
LIVE_AREA_CODE_POOL_ID = 3

LIVE_PAGE_REQUEST = {
    "type": "page",
    "properties": {
        "title": "Page One",
        "url": "http://localhost:8080/one?pl=1",
        "pool_id": LIVE_AREA_CODE_POOL_ID,
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


class FakeRedisConn:
    def __init__(self):
        self.storage = {}
        self.expirations = {}

    def get(self, key):
        return self.storage.get(key, None)

    def setex(self, key, ttl_seconds, value):
        self.storage[key] = value
        self.expirations[key] = ttl_seconds


class FakeGeoIPClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def city(self, ip):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


def test_get_area_codes_from_context_uses_geoip_without_source_requirement(
    monkeypatch,
):
    monkeypatch.setattr(settings, "SESSION_SOURCE_PARAM", None)
    monkeypatch.setattr(
        zar_endpoints,
        "geoip_area_codes_from_ip",
        lambda ip: ["401", "339"],
    )

    context = {
        "ip": "8.8.8.8",
        "latest_context": {"url": "http://localhost:8080/one?pl=1&gip=1"},
    }

    assert zar_endpoints.get_area_codes_from_context(context) == ["401", "339"]
    assert context["latest_context"]["area_code_source"] == "geoip"


def test_get_area_codes_from_context_disables_geoip_without_gip_param(
    monkeypatch,
):
    monkeypatch.setattr(settings, "SESSION_SOURCE_PARAM", None)
    monkeypatch.setattr(
        zar_endpoints,
        "geoip_area_codes_from_ip",
        lambda ip: (_ for _ in ()).throw(AssertionError("geoip should not run")),
    )

    context = {
        "ip": "8.8.8.8",
        "latest_context": {"url": "http://localhost:8080/one?pl=1"},
    }

    assert zar_endpoints.get_area_codes_from_context(context) is None


def test_get_area_codes_from_context_disables_geoip_with_gip_zero(
    monkeypatch,
):
    monkeypatch.setattr(settings, "SESSION_SOURCE_PARAM", None)
    monkeypatch.setattr(
        zar_endpoints,
        "geoip_area_codes_from_ip",
        lambda ip: (_ for _ in ()).throw(AssertionError("geoip should not run")),
    )

    context = {
        "ip": "8.8.8.8",
        "latest_context": {"url": "http://localhost:8080/one?pl=1&gip=0"},
    }

    assert zar_endpoints.get_area_codes_from_context(context) is None


def test_get_area_codes_from_context_requires_session_source_param_for_geoip(
    monkeypatch,
):
    monkeypatch.setattr(settings, "SESSION_SOURCE_PARAM", "src")
    monkeypatch.setattr(
        zar_endpoints,
        "geoip_area_codes_from_ip",
        lambda ip: (_ for _ in ()).throw(AssertionError("geoip should not run")),
    )

    context = {
        "ip": "8.8.8.8",
        "latest_context": {"url": "http://localhost:8080/one?pl=1&gip=1"},
    }

    assert zar_endpoints.get_area_codes_from_context(context) is None


def test_get_area_codes_from_context_requires_non_empty_session_source_for_geoip(
    monkeypatch,
):
    monkeypatch.setattr(settings, "SESSION_SOURCE_PARAM", "src")
    monkeypatch.setattr(
        zar_endpoints,
        "geoip_area_codes_from_ip",
        lambda ip: (_ for _ in ()).throw(AssertionError("geoip should not run")),
    )

    context = {
        "ip": "8.8.8.8",
        "latest_context": {"url": "http://localhost:8080/one?pl=1&src=&gip=1"},
    }

    assert zar_endpoints.get_area_codes_from_context(context) is None


def test_get_area_codes_from_context_allows_non_empty_session_source_for_geoip(
    monkeypatch,
):
    monkeypatch.setattr(settings, "SESSION_SOURCE_PARAM", "src")
    monkeypatch.setattr(
        zar_endpoints,
        "geoip_area_codes_from_ip",
        lambda ip: ["401"],
    )

    context = {
        "ip": "8.8.8.8",
        "latest_context": {"url": "http://localhost:8080/one?pl=1&src=abc&gip=1"},
    }

    assert zar_endpoints.get_area_codes_from_context(context) == ["401"]
    assert context["latest_context"]["area_code_source"] == "geoip"


def test_geoip_area_codes_from_ip_caches_minimal_area_codes_in_redis(monkeypatch):
    fake_conn = FakeRedisConn()
    fake_response = SimpleNamespace(
        country=SimpleNamespace(iso_code="US"),
        subdivisions=SimpleNamespace(most_specific=SimpleNamespace(iso_code="RI")),
        location=SimpleNamespace(latitude=41.82, longitude=-71.41),
    )
    fake_client = FakeGeoIPClient(response=fake_response)

    monkeypatch.setattr(geo_module, "get_number_pool_conn", lambda: fake_conn)
    monkeypatch.setattr(geo_module, "get_maxmind_geoip_client", lambda: fake_client)
    monkeypatch.setattr(
        geo_module,
        "_rank_area_codes_for_geoip_location",
        lambda country, subdivision, lat, lon: ["401", "339"],
    )

    first_result = geo_module.geoip_area_codes_from_ip("8.8.8.8")
    second_result = geo_module.geoip_area_codes_from_ip("8.8.8.8")

    cache_key = f"{geo_module.MAXMIND_GEOIP_CACHE_KEY_PREFIX}:8.8.8.8"
    assert first_result == ["401", "339"]
    assert second_result == ["401", "339"]
    assert fake_client.calls == 1
    assert (
        fake_conn.expirations[cache_key] == geo_module.MAXMIND_GEOIP_CACHE_TTL_SECONDS
    )
    assert fake_conn.storage[cache_key] == json.dumps(["401", "339"])


def test_geoip_area_codes_from_ip_negative_caches_address_not_found(monkeypatch):
    fake_conn = FakeRedisConn()
    fake_client = FakeGeoIPClient(error=geoip2.errors.AddressNotFoundError("not found"))

    monkeypatch.setattr(geo_module, "get_number_pool_conn", lambda: fake_conn)
    monkeypatch.setattr(geo_module, "get_maxmind_geoip_client", lambda: fake_client)

    first_result = geo_module.geoip_area_codes_from_ip("8.8.8.8")
    second_result = geo_module.geoip_area_codes_from_ip("8.8.8.8")

    cache_key = f"{geo_module.MAXMIND_GEOIP_CACHE_KEY_PREFIX}:8.8.8.8"
    assert first_result is None
    assert second_result == []
    assert fake_client.calls == 1
    assert fake_conn.storage[cache_key] == json.dumps([])


def test_rank_area_codes_for_geoip_location_returns_single_candidate_when_close(
    monkeypatch,
):
    monkeypatch.setattr(
        geo_module,
        "AREA_CODES",
        {
            "401": {
                "Metro Area": "Providence, RI",
                "Latitude": "41.82",
                "Longitude": "-71.41",
                "Population": 1100000,
            },
            "508": {
                "Metro Area": "Worcester, MA",
                "Latitude": "42.26",
                "Longitude": "-71.8",
                "Population": 1200000,
            },
            "774": {
                "Metro Area": "Worcester, MA",
                "Latitude": "42.26",
                "Longitude": "-71.8",
                "Population": 1200000,
            },
        },
    )

    area_codes = geo_module._rank_area_codes_for_geoip_location(
        "US",
        "RI",
        41.82,
        -71.41,
    )

    assert area_codes == ["401"]


def test_rank_area_codes_for_geoip_location_returns_up_to_three_candidates_when_far(
    monkeypatch,
):
    monkeypatch.setattr(
        geo_module,
        "AREA_CODES",
        {
            "401": {
                "Metro Area": "Providence, RI",
                "Latitude": "41.82",
                "Longitude": "-71.41",
                "Population": 1100000,
            },
            "508": {
                "Metro Area": "Worcester, MA",
                "Latitude": "42.26",
                "Longitude": "-71.8",
                "Population": 1200000,
            },
            "774": {
                "Metro Area": "Worcester, MA",
                "Latitude": "42.26",
                "Longitude": "-71.8",
                "Population": 1000000,
            },
            "339": {
                "Metro Area": "Boston, MA",
                "Latitude": "42.36",
                "Longitude": "-71.06",
                "Population": 2000000,
            },
            "781": {
                "Metro Area": "Boston, MA",
                "Latitude": "42.36",
                "Longitude": "-71.06",
                "Population": 1600000,
            },
        },
    )

    area_codes = geo_module._rank_area_codes_for_geoip_location(
        "US",
        "RI",
        36.0,
        -80.0,
    )

    assert area_codes == ["401", "508", "774"]


def test_live_geoip_area_codes_for_rhode_island_ip(client):
    if not (settings.MAXMIND_GEOIP_ACCOUNT_ID and settings.MAXMIND_GEOIP_LICENSE_KEY):
        pytest.skip("MaxMind credentials are not configured")

    if not zar_endpoints.pool_api:
        pytest.skip("Number pool is not available")

    conn = geo_module.get_number_pool_conn()
    if not conn:
        pytest.skip("Redis connection is not available")

    conn.delete(f"{geo_module.MAXMIND_GEOIP_CACHE_KEY_PREFIX}:{LIVE_MAXMIND_TEST_IP}")
    zar_endpoints.pool_api._reset_pool(LIVE_AREA_CODE_POOL_ID, preserve=False)
    client.cookies.clear()

    req = copy.deepcopy(LIVE_PAGE_REQUEST)
    url = req["properties"]["url"]
    url = f"{url}&gip=1"
    if settings.SESSION_SOURCE_PARAM:
        url = f"{url}&{settings.SESSION_SOURCE_PARAM}=integration"

    req["properties"]["url"] = url
    req["properties"]["pool_context"] = {"url": url}

    start = time.time()
    response = client.post(
        f"{settings.API_V2_STR}/page",
        json=req,
        headers={"x-forwarded-for": LIVE_MAXMIND_TEST_IP},
    )
    info(f"Live geoip request took {time.time() - start:.2f} seconds")

    assert response.status_code == 200, response.text

    data = response.json()
    pool_data = data.get("pool_data", None)
    assert pool_data
    number = pool_data.get("number", "")
    assert number.startswith("401")

    number_ctx = zar_endpoints.pool_api.get_pool_number_context(number)
    assert number_ctx

    latest_context = number_ctx.get("request_context", {}).get("latest_context", {})
    assert latest_context.get("area_code_source") == "geoip"
