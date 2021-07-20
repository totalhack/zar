from sqlalchemy import Column, Boolean, BigInteger, Text, String, DateTime
from sqlalchemy.sql import func

from app.db.base_class import Base


class Page(Base):
    id = Column(BigInteger, primary_key=True)
    vid = Column(String(36), index=True, nullable=True)
    sid = Column(String(36), index=True, nullable=True)
    cid = Column(String(36), index=True, nullable=True)
    uid = Column(String(64), index=True, nullable=True)
    host = Column(String(256), nullable=True)
    ip = Column(String(128), nullable=True)
    user_agent = Column(String(512), nullable=True)
    referer = Column(String(2048), nullable=True)
    properties = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class Track(Base):
    id = Column(BigInteger, primary_key=True)
    event = Column(String(64), index=True)
    vid = Column(String(36), index=True, nullable=True)
    sid = Column(String(36), index=True, nullable=True)
    cid = Column(String(36), index=True, nullable=True)
    uid = Column(String(64), index=True, nullable=True)
    host = Column(String(256), nullable=True)
    ip = Column(String(128), nullable=True)
    user_agent = Column(String(512), nullable=True)
    referer = Column(String(2048), nullable=True)
    properties = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class TrackCall(Base):
    __tablename__ = "track_call"

    id = Column(BigInteger, primary_key=True)
    call_id = Column(String(64), index=True, nullable=False)
    sid = Column(String(36), index=True, nullable=True)
    call_from = Column(String(15), nullable=False)
    call_to = Column(String(15), nullable=False)
    number_context = Column(Text, nullable=True)
    from_route_cache = Column(Boolean, nullable=True, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class Pools(Base):
    __tablename__ = "pools"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(64), unique=True)
    active = Column(Boolean, default=False)
    properties = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class PoolNumbers(Base):
    __tablename__ = "pool_numbers"

    pool_id = Column(BigInteger, primary_key=True, autoincrement=False)
    number = Column(String(20), primary_key=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)