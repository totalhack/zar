from typing import Dict, Any
from pydantic import BaseModel
from tlbx import st, raiseifnot


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
class PageRequestBody(BaseModel):
    type: str
    zar: Dict[str, str]
    anonymousId: str = None
    userId: str = None
    properties: Dict[str, Any] = None
    options: Dict[str, Any] = None
    meta: Dict[str, Any] = None


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
class TrackRequestBody(BaseModel):
    type: str
    event: str
    zar: Dict[str, str]
    anonymousId: str = None
    userId: str = None
    properties: Dict[str, Any] = None
    options: Dict[str, Any] = None
    meta: Dict[str, Any] = None

