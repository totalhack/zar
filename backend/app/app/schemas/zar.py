from typing import Dict, Any
from pydantic import BaseModel


class PageRequestBody(BaseModel):
    type: str
    anonymousId: str = None
    userId: str = None
    properties: Dict[str, Any] = None
    options: Dict[str, Any] = None
    meta: Dict[str, Any] = None


class TrackRequestBody(BaseModel):
    type: str
    event: str
    anonymousId: str = None
    userId: str = None
    properties: Dict[str, Any] = None
    options: Dict[str, Any] = None
    meta: Dict[str, Any] = None

