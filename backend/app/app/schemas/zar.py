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


class TrackCallRequestBody(BaseModel):
    key: str
    call_id: str
    call_from: str
    call_to: str


class NumberPoolRequestBody(BaseModel):
    pool_id: int
    number: str = None
    context: Dict[str, Any] = None
    properties: Dict[str, Any] = None
    options: Dict[str, Any] = None
    meta: Dict[str, Any] = None


class UpdateNumberRequestBody(BaseModel):
    pool_id: int
    number: str
    context: Dict[str, Any]
    properties: Dict[str, Any] = None
    options: Dict[str, Any] = None
    meta: Dict[str, Any] = None


class NumberPoolCacheValue(BaseModel):
    pool_id: int
    leased_at: float
    renewed_at: float
    request_context: Dict[str, Any] = None
