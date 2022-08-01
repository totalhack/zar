from typing import Generator

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
