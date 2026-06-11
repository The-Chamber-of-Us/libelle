from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import auth as auth_routes
from api.routes import dashboard as dashboard_routes
from api.routes import health as health_routes
from api.routes import intake as intake_routes
from api.routes import resumes as resumes_routes
from config import ALLOWED_ORIGINS, MAX_PDF_MB
from validator import validate_sheet_schema


app = FastAPI(title="Libelle Backend API")


if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def _startup_log():
    print("[STARTUP] Libelle backend booted")
    print(f"[STARTUP] MAX_PDF_MB={MAX_PDF_MB}")
    print(f"[STARTUP] ALLOWED_ORIGINS={ALLOWED_ORIGINS}")


@app.on_event("startup")
def _startup_validate_schema():
    validate_sheet_schema()


# -----------------------------
# Error Handling (JSON only)
# -----------------------------
def _json_error(status_code: int, payload: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return _json_error(exc.status_code, exc.detail)
    return _json_error(
        exc.status_code,
        {"status": "error", "code": "HTTP_EXCEPTION", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    fields: Dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", [])
        msg = err.get("msg", "Invalid")
        if len(loc) >= 2:
            fields[str(loc[-1])] = msg
        else:
            fields["request"] = msg

    return _json_error(
        422,
        {"status": "error", "code": "VALIDATION_ERROR", "fields": fields or {"request": "Invalid request"}},
    )


# -----------------------------
# Routes
# -----------------------------
app.include_router(health_routes.router)
app.include_router(intake_routes.router)
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(resumes_routes.router)
