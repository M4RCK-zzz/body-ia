from collections.abc import Awaitable, Callable
from uuid import uuid4
from fastapi import FastAPI, Request, Response

def register_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = (request.headers.get("X-Request-ID") or uuid4().hex)[:64]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response