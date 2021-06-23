from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tlbx import st, pp

from app.core.config import settings
from app.number_pool import NumberPoolResponseStatus


SAMPLE_PAGE_REQUEST = {
    "type": "page",
    "properties": {
        "title": "Page One",
        "url": "http://localhost:8080/one",
        "path": "/one",
        "hash": "",
        "search": "",
        "width": 1680,
        "height": 619,
        "referrer": "http://localhost:8080/one",
        "zar": {
            "cid": {
                "id": "29d7dfba-47ed-4305-ad91-e0625101afbf",
                "t": 1604071692653,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
            "sid": {
                "id": "d3901827-c280-446e-bd8f-fcf8deb12f2d",
                "t": 1604071692653,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
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


def test_endpoint_page(client: TestClient) -> None:
    resp = client.post(f"{settings.API_V1_STR}/page", json=SAMPLE_PAGE_REQUEST)
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("id", None)


SAMPLE_TRACK_REQUEST = {
    "type": "track",
    "event": "event1",
    "properties": {
        "attr1": "val1",
        "attr2": "val2",
        "zar": {
            "cid": {
                "id": "29d7dfba-47ed-4305-ad91-e0625101afbf",
                "t": 1604071705447,
                "origReferrer": "http://localhost:8080/one",
                "isNew": False,
                "visits": 3,
            },
            "sid": {
                "id": "d3901827-c280-446e-bd8f-fcf8deb12f2d",
                "t": 1604071692653,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
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
    "pool_id": "1",
    "number": None,
    "context": {"foo": "bar", "baz": "bar"},
    "properties": {
        "attr1": "val1",
        "attr2": "val2",
        "zar": {
            "cid": {
                "id": "29d7dfba-47ed-4305-ad91-e0625101afbf",
                "t": 1604071705447,
                "origReferrer": "http://localhost:8080/one",
                "isNew": False,
                "visits": 3,
            },
            "sid": {
                "id": "d3901827-c280-446e-bd8f-fcf8deb12f2d",
                "t": 1604071692653,
                "origReferrer": "http://localhost:8080/one",
                "isNew": True,
                "visits": 1,
            },
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


def test_endpoint_number_pool(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_V1_STR}/number_pool", json=SAMPLE_NUMBER_POOL_REQUEST
    )
    assert resp.status_code == 200
    data = resp.json()
    pp(data)
    assert data.get("status", None) == NumberPoolResponseStatus.SUCCESS