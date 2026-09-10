"""
Legal Metrology Compliance Auditing System - API entry point.

This module is deliberately thin: application wiring only. Rule logic lives in
`app/engine`, OCR in `app/core/ocr.py`, persistence in `app/db`, and every route
in `app/api/v1`. The previous single-file `main.py` mixed all four.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, inspections, reports, rules
from app.config import settings
from app.core.security import hash_password
from app.db import repositories as repo
from app.db.store import backend_name
from app.models import Role

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("legal_metrology_api")


def _bootstrap_admin() -> None:
    """
    Seeds the first administrator when the user store is empty and a bootstrap
    password is configured. Without this a fresh deployment has no way in; with a
    blank password we do nothing, because a well-known default credential on a
    public URL is worse than an empty system.
    """
    try:
        if repo.users.count() > 0:
            return
        password = settings.BOOTSTRAP_ADMIN_PASSWORD.strip()
        if not password:
            logger.info(
                "No users yet. Set BOOTSTRAP_ADMIN_PASSWORD, or register the first "
                "account via POST /api/v1/auth/register (the first account becomes ADMIN)."
            )
            return
        repo.users.create(
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            password_hash=hash_password(password),
            full_name="System Administrator",
            role=Role.ADMIN.value,
            designation="Administrator",
            jurisdiction="National",
        )
        logger.info("Bootstrap administrator created: %s", settings.BOOTSTRAP_ADMIN_EMAIL)
    except Exception as exc:
        logger.warning("Bootstrap administrator not created: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("%s v%s starting (%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    logger.info("Document store: %s", backend_name())
    _bootstrap_admin()
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Automated compliance auditing of pre-packaged commodities under the Legal "
        "Metrology Act, 2009 and the Legal Metrology (Packaged Commodities) Rules, 2011.\n\n"
        "All routes except `/api/v1/health` and `/api/v1/auth/*` require a bearer token."
    ),
    lifespan=lifespan,
)

# Explicit origin allowlist. A wildcard is rejected in config because the API sends
# credentials, and browsers silently drop credentialed requests to a "*" origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(inspections.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(rules.router, prefix=API_PREFIX)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.get(API_PREFIX + "/health", tags=["System"])
def health():
    """Unauthenticated liveness probe used by the frontend to show connection state."""
    from app.core.ocr import engine_name
    from app.db.db_manager import db_manager

    return {
        "status": "online",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "document_store": backend_name(),
        "ocr_engine": engine_name(),
        "rules_loaded": len(db_manager.master_rules),
        "registered_users": repo.users.count(),
    }


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": API_PREFIX + "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
