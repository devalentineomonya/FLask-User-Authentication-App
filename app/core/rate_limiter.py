import logging
from typing import Callable

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class RateLimiter(BaseHTTPMiddleware):
    """
    Fixed-window rate limit per client IP and path, stored in Redis.
    If Redis is unreachable the request is allowed through.
    """

    def __init__(
        self,
        app,
        redis_url: str = settings.REDIS_URL,
        rate_limit_per_minute: int = settings.RATE_LIMIT_PER_MINUTE
    ):
        super().__init__(app)
        self.redis = redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
        self.rate_limit = rate_limit_per_minute
        self.window = 60

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}:{request.url.path}"

        try:
            current = await self.redis.incr(key)
            if current == 1:
                await self.redis.expire(key, self.window)
        except redis.RedisError as e:
            logger.warning("Rate limiter unavailable: %s", e)
            return await call_next(request)

        if current > self.rate_limit:
            return Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(self.window)}
            )

        return await call_next(request)
