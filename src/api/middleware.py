import time
import uuid
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        start_time = time.perf_counter()
        
        # Log request
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
        )

        try:
            response: Response = await call_next(request)
        except Exception as e:
            process_time = time.perf_counter() - start_time
            logger.exception(
                "http_request_failed",
                path=request.url.path,
                method=request.method,
                duration=f"{process_time:.4f}s",
                error=str(e),
            )
            raise e

        process_time = time.perf_counter() - start_time
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"

        logger.info(
            "http_response",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=f"{process_time:.4f}s",
        )

        return response
