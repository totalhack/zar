from typing import Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator


USER_ID_TYPES = {
    "phone",
    "email",
    "session_id",
}


class PageRequestBody(BaseModel):
    type: str
    anonymousId: Union[str, None] = Field(default=None)
    userId: Union[str, None] = Field(default=None)
    properties: Union[Dict[str, Any], None] = Field(default=None)
    options: Union[Dict[str, Any], None] = Field(default=None)
    meta: Union[Dict[str, Any], None] = Field(default=None)


class TrackRequestBody(BaseModel):
    type: str
    event: str
    anonymousId: Union[str, None] = Field(default=None)
    userId: Union[str, None] = Field(default=None)
    properties: Union[Dict[str, Any], None] = Field(default=None)
    options: Union[Dict[str, Any], None] = Field(default=None)
    meta: Union[Dict[str, Any], None] = Field(default=None)


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

    @field_validator("id_type")
    def validate_id_type(cls, v):
        if v not in USER_ID_TYPES:
            raise ValueError(f"invalid id_type: {v}")
        return v


class GetUserContextRequestParams(BaseModel):
    key: str
    user_id: str
    id_type: str

    @field_validator("id_type")
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
    number: Union[str, None] = Field(default=None)
    context: Union[Dict[str, Any], None] = Field(default=None)
    properties: Union[Dict[str, Any], None] = Field(default=None)
    options: Union[Dict[str, Any], None] = Field(default=None)
    meta: Union[Dict[str, Any], None] = Field(default=None)


class UpdateNumberRequestBody(BaseModel):
    pool_id: int
    number: str
    context: Dict[str, Any]
    properties: Union[Dict[str, Any], None] = Field(default=None)
    options: Union[Dict[str, Any], None] = Field(default=None)
    meta: Union[Dict[str, Any], None] = Field(default=None)


class NumberPoolCacheValue(BaseModel):
    pool_id: int
    leased_at: float
    renewed_at: float
    request_context: Union[Dict[str, Any], None] = Field(default=None)
