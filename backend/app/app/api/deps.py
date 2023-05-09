from typing import Generator

from fastapi import HTTPException, Request
from tlbx import json, st

from app.db.session import SessionLocal, engine


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_conn() -> Generator:
    try:
        conn = engine.connect()
        yield conn
    finally:
        conn.close()


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
        data = json.loads(data)
    else:
        raise HTTPException(status_code=422, detail="Invalid content")
    return data
