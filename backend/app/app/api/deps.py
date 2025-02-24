from typing import Generator, AsyncGenerator

from fastapi import HTTPException, Request
from tlbx import json, st, warn

from app.db.session import database, SessionLocal


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


async def get_conn() -> AsyncGenerator:
    async with database.connection() as conn:
        yield conn


# For use in sync endpoints: https://github.com/tiangolo/fastapi/issues/393#issuecomment-584408572
async def get_body_data(request: Request):
    data = None
    if "content-type" not in request.headers:
        raise HTTPException(status_code=422, detail="Missing content type")
    if request.headers["content-type"] == "application/x-www-form-urlencoded":
        data = await request.form()
    elif request.headers["content-type"] == "application/json":
        data = await request.json()
    elif "text/plain" in request.headers["content-type"]:
        data = await request.body()
        try:
            data = json.loads(data)
        except:
            warn("Error parsing body JSON")
            warn(data)
            raise
    else:
        raise HTTPException(status_code=422, detail="Invalid content")
    return data
