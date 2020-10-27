from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tlbx import st, pp

from app.core.config import settings


# {
#     "type": "page",
#     "properties": {
#         "title": "Home Page",
#         "url": "http://localhost:8080/",
#         "path": "/",
#         "hash": "",
#         "search": "",
#         "width": 1680,
#         "height": 482,
#     },
#     "options": {},
#     "userId": null,
#     "anonymousId": "ffcd2d97-13aa-48c4-889b-292dc27d3581",
#     "meta": {"timestamp": 1603396806910},
#     "zar": {
#         "cid": "ffcd2d97-13aa-48c4-889b-292dc27d3581",
#         "sid": "ec6127ae-a8b9-40cd-9a7c-9e2bd5e54b32",
#         "vid": "kgl9267r.c3q45pzsdpa",
#     },
# }


def test_page(client: TestClient) -> None:
    resp = client.post(
        f"{settings.API_V1_STR}/page",
        json={"id": "foobar", "title": "Foo Bar", "description": "The Foo Barters"},
    )
    assert resp.status_code == 200
    data = resp.json()
    pp(data)


# {
#   "type": "track",
#   "event": "event1",
#   "properties": {
#     "attr1": "val1",
#     "attr2": "val2",
#     "anonymousId": "ffcd2d97-13aa-48c4-889b-292dc27d3581",
#     "category": "All"
#   },
#   "options": {},
#   "userId": null,
#   "anonymousId": "ffcd2d97-13aa-48c4-889b-292dc27d3581",
#   "meta": {
#     "timestamp": 1603726158141
#   },
#   "zar": {
#     "cid": "ffcd2d97-13aa-48c4-889b-292dc27d3581",
#     "sid": "65fc76f6-6b3d-4e3e-825e-b69460902b7c",
#     "vid": "kgqoznx2.zmsceokwq09"
#   }
# }

# def test_track(client: TestClient) -> None:
#     resp = client.post(
#         f"{settings.API_V1_STR}/track",
#         json={"id": "foobar", "title": "Foo Bar", "description": "The Foo Barters"},
#     )
#     assert resp.status_code == 200
#     data = resp.json()
#     pp(data)
