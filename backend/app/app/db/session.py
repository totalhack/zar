from databases import Database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=5,  # Smaller pool for legacy sync connections
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


ASYNC_DATABASE_URI = settings.SQLALCHEMY_DATABASE_URI.replace(
    "mysql+pymysql", "mysql+aiomysql"
)
database = Database(ASYNC_DATABASE_URI, min_size=5, max_size=20)
