import os
import logging
import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USE_REDIS = os.getenv("USE_REDIS", "true").lower() == "true"

_redis_client = None


def get_redis_client():
    """
    Trả về Redis client nếu kết nối thành công và USE_REDIS=true.
    Trả về None nếu Redis bị vô hiệu hóa hoặc kết nối thất bại.
    Caller phải tự kiểm tra giá trị trả về để áp dụng logic RAM dự phòng.
    """
    global _redis_client
    if not USE_REDIS:
        return None

    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            logger.warning("[Redis] Lost connection to Redis. Will retry on next call.")
            _redis_client = None

    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        client.ping()
        _redis_client = client
        logger.info(f"[Redis] Connected successfully to {REDIS_HOST}:{REDIS_PORT}")
        return _redis_client
    except Exception as e:
        logger.warning(f"[Redis] Could not connect: {e}. Fallback to RAM memory will be used.")
        _redis_client = None
        return None
