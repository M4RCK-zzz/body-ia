from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

def _field_name(loc: tuple[int | str, ...]) -> str:
    parts = loc[1:] if len(loc) > 1 else loc
    return ".".join(str(p) for p in parts)

def register_validation_handler(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": _field_name(tuple(err["loc"])),
                "message": str(err["msg"]).removeprefix("Value error, "),
            }
            for err in exc.errors()
        ]
        summary = "; ".join(
            f"{f['field']}: {f['message']}" if f["field"] else f["message"] for f in fields
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": f"Datos inválidos. {summary}",
                    "fields": fields,
                }
            },
        )