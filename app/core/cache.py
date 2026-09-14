import hashlib
import json
import logging
from typing import Callable

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}
GENERATION_KEY = "cache:generation"


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Caches successful GET responses in Redis.

    Responses are cached per caller (keyed on a hash of the Authorization header)
    so role-filtered data is never served to a different user. Any successful
    write bumps a generation counter, which invalidates every cached entry.
    Redis errors are logged and the request is served uncached.
    """

    def __init__(
        self,
        app,
        redis_url: str = settings.REDIS_URL,
        ttl: int = settings.CACHE_TTL_SECONDS
    ):
        super().__init__(app)
        self.redis = redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
        self.ttl = ttl

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        if request.method != "GET":
            response = await call_next(request)
            if 200 <= response.status_code < 300:
                await self._invalidate()
            return response

        cache_key = await self._cache_key(request)
        if cache_key is None:
            return await call_next(request)

        try:
            cached_response = await self.redis.get(cache_key)
        except redis.RedisError as e:
            logger.warning("Cache read failed: %s", e)
            return await call_next(request)

        if cached_response:
            cached_data = json.loads(cached_response)
            return Response(
                content=cached_data["content"],
                status_code=cached_data["status_code"],
                headers={**cached_data["headers"], "X-Cache": "HIT"},
            )

        response = await call_next(request)

        if response.status_code != 200:
            return response

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        try:
            await self.redis.setex(
                cache_key,
                self.ttl,
                json.dumps({
                    "content": response_body.decode(),
                    "status_code": response.status_code,
                    "headers": headers,
                })
            )
        except redis.RedisError as e:
            logger.warning("Cache write failed: %s", e)

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers={**headers, "X-Cache": "MISS"},
        )

    async def _cache_key(self, request: Request) -> str | None:
        try:
            generation = await self.redis.get(GENERATION_KEY) or b"0"
        except redis.RedisError as e:
            logger.warning("Cache unavailable: %s", e)
            return None
        caller = hashlib.sha256(request.headers.get("authorization", "").encode()).hexdigest()
        return f"cache:{generation.decode()}:{caller}:{request.url.path}?{request.url.query}"

    async def _invalidate(self) -> None:
        try:
            await self.redis.incr(GENERATION_KEY)
        except redis.RedisError as e:
            logger.warning("Cache invalidation failed: %s", e)
