from sqlalchemy import Column, BigInteger, Text, String, DateTime
from sqlalchemy.sql import func

from app.db.base_class import Base


class Page(Base):
    id = Column(BigInteger, primary_key=True)
    vid = Column(String(24), index=True, nullable=True)
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
    vid = Column(String(24), index=True, nullable=True)
    sid = Column(String(36), index=True, nullable=True)
    cid = Column(String(36), index=True, nullable=True)
    uid = Column(String(64), index=True, nullable=True)
    host = Column(String(256), nullable=True)
    ip = Column(String(128), nullable=True)
    user_agent = Column(String(512), nullable=True)
    referer = Column(String(2048), nullable=True)
    properties = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
