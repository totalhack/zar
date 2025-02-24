from typing import List, Union

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    ENABLE_DOCS: bool = True

    API_V1_STR: str = "/api/v1"
    API_V2_STR: str = "/api/v2"
    SERVER_NAME: str
    SERVER_HOST: AnyHttpUrl
    # BACKEND_CORS_ORIGINS is a JSON-formatted list of origins
    # e.g: '["http://localhost", "http://localhost:4200", "http://localhost:3000", \
    # "http://localhost:8080"]'
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    PROJECT_NAME: str
    SQLALCHEMY_DATABASE_URI: str

    REDIS_HOST: str
    REDIS_PASSWORD: str

    ROLLBAR_ENABLED: bool = True
    ROLLBAR_ENV: str
    ROLLBAR_KEY: str

    NUMBER_POOL_ENABLED: bool = False
    NUMBER_POOL_KEY: str

    ALLOW_BOTS: bool = False

    SESSION_RESET_PARAM: Union[str, None] = None

    model_config = {"case_sensitive": True}


settings = Settings()
