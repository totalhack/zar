import logging

from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.config import settings
from app.db.session import SessionLocal
from app.number_pool import NumberPoolAPI, NumberPoolUnavailable


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def init_db() -> None:
    try:
        db = SessionLocal()
        # Try to create session to check if DB is awake
        db.execute("SELECT 1")
    except Exception as e:
        logger.error(e)
        raise e


def init_number_pool():
    try:
        pool_api = NumberPoolAPI()
        pool_api.init_pools()
    except NumberPoolUnavailable as e:
        logger.warning(str(e))
    except Exception as e:
        if "doesn't exist" not in str(e):
            raise
        logger.warning("Table(s) don't exist!")


def main() -> None:
    logger.info("Initializing service")
    init_db()
    if settings.NUMBER_POOL_ENABLED:
        init_number_pool()
    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
