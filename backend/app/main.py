from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.logging import RequestLoggingMiddleware, logger, setup_logging
from app.core.security import AppException, limiter
from app.routers import (
    auth,
    backup,
    customers,
    dashboard,
    payments,
    products,
    purchases,
    reports,
    sales,
    suppliers,
    users,
)

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "REST API backend for the Inam Ur Rehman Commission Shop distribution, "
        "inventory, sales and ledger management system."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production ke liye specific origins rakhein, dev ke liye "*" safe hai
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ---------------- Exception handlers (consistent error shape) ----------------
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests, please slow down", "error_code": "RATE_LIMITED"},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors()), "error_code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception('"unhandled exception"')
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
    )


# ---------------- Health ----------------
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


# ---------------- Router ----------------
API_PREFIX = "/api/v1"
for module in (
    auth,
    users,
    products,
    customers,
    suppliers,
    purchases,
    sales,
    payments,
    reports,
    dashboard,
    backup,
):
    app.include_router(module.router, prefix=API_PREFIX)

app.include_router(customers.ledger_router, prefix=API_PREFIX)
