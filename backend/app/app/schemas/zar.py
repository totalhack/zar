from typing import Dict, Any, List
from pydantic import BaseModel, validator


USER_ID_TYPES = {
    "phone",
    "email",
    "session_id",
}


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


class UpdateUserContextRequestBody(BaseModel):
    key: str
    user_id: str
    id_type: str
    context: Dict[str, Any]

    @validator("id_type")
    def validate_id_type(cls, v):
        if v not in USER_ID_TYPES:
            raise ValueError(f"invalid id_type: {v}")
        return v


class GetUserContextRequestParams(BaseModel):
    key: str
    user_id: str
    id_type: str

    @validator("id_type")
    def validate_id_type(cls, v):
        if v not in USER_ID_TYPES:
            raise ValueError(f"invalid id_type: {v}")
        return v


class GetStaticNumberContextRequestParams(BaseModel):
    key: str
    number: str


class StaticNumberContext(BaseModel):
    number: str
    context: Dict[str, Any]


class SetStaticNumberContextsRequestBody(BaseModel):
    key: str
    contexts: List[StaticNumberContext]


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
