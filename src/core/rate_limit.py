import time
from fastapi import Request, HTTPException, status
from redis.asyncio import Redis
from src.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

class RateLimiter:
    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)

    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        """
        Fixed window rate limiting using Redis.
        key: Unique key (e.g., user_id or IP)
        limit: Max requests allowed in the window
        window: Time window in seconds
        """
        current_time = int(time.time())
        window_key = f"rate_limit:{key}:{current_time // window}"
        
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(window_key)
            pipe.expire(window_key, window)
            results = await pipe.execute()
            
        count = results[0]
        return count > limit

def get_rate_limiter():
    redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
    return RateLimiter(redis_url)

async def rate_limit_dependency(
    request: Request,
    limit: int = 10,
    window: int = 60
):
    # Try to get user_id if authenticated, otherwise fallback to IP
    user_id = getattr(request.state, "user_id", request.client.host)
    key = f"{request.url.path}:{user_id}"
    
    limiter = get_rate_limiter()
    if await limiter.is_rate_limited(key, limit, window):
        logger.warning("rate_limit_exceeded", key=key, limit=limit, window=window)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
