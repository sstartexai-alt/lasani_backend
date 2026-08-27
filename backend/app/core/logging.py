import logging
import os
import time
import uuid
from logging.handlers import RotatingFileHandler

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings

logger = logging.getLogger("app")


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    if logger.handlers:
        return

    fmt = logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}'
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    if settings.LOG_FILE:
        os.makedirs(os.path.dirname(settings.LOG_FILE) or ".", exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)


def _json_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        # Best-effort user id extraction for audit logging (never blocks the request).
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                from app.core.security import decode_token

                request.state.user_id = int(decode_token(auth[7:]).get("sub"))
            except Exception:
                request.state.user_id = None

        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            user_id = getattr(request.state, "user_id", None)
            status = response.status_code if response is not None else 500
            payload = (
                f'{{"request_id":"{request_id}",'
                f'"user_id":{user_id if user_id is not None else "null"},'
                f'"method":"{request.method}",'
                f'"path":"{_json_escape(request.url.path)}",'
                f'"status":{status},'
                f'"latency_ms":{latency_ms}}}'
            )
            logger.info(payload)
            if response is not None:
                response.headers["X-Request-ID"] = request_id
