import time
from functools import wraps
from tools.utils.logger import get_logger

logger = get_logger("RetryManager")

def retry_with_backoff(retries: int = 3, initial_delay: float = 2.0, backoff_factor: float = 2.0, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == retries:
                        logger.error(f"[{func.__name__}] Failed after {retries} attempts: {e}", exc_info=True)
                        raise
                    logger.warning(f"[{func.__name__}] Error: {e}. Retrying ({attempt}/{retries}) in {delay}s...")
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator
