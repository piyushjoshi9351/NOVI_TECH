import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.database import Base, engine
from app.core.config import PROJECT_ROOT, settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("novi")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Idempotent: ensure every registered model (incl. onboarding_sessions) exists.
    import app.models  # noqa: F401  (registers all tables on Base.metadata)

    from app.db.run_migrations import check_critical_columns, run_migrations

    Base.metadata.create_all(bind=engine)
    from app.m3.db.models import Base as M3Base
    M3Base.metadata.create_all(bind=engine)
    run_migrations()
    check_critical_columns()

    # Idempotent safety net: keep the onboarding lookup catalog (countries /
    # curriculums / grades / subjects) present. The flow is broken without it.
    try:
        from app.core.database import SessionLocal
        from app.db.seed_onboarding import seed_onboarding

        with SessionLocal() as _db:
            seed_onboarding(_db)
    except Exception as exc:  # pragma: no cover - never block boot over a seed
        logger.warning("onboarding catalog seed skipped: %s", exc)

    yield


FRONTEND_DIR = Path(settings.FRONTEND_DIR)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="NOVI — The Operating System for Student Success",
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Google OAuth callback must live at the exact (unversioned) redirect URI registered
# in Google Cloud Console — e.g. http://localhost:8000/api/auth/google/callback.
from app.api import google_auth  # noqa: E402

app.include_router(google_auth.router, prefix="/api", include_in_schema=False)

# Internal, service-to-service onboarding endpoints (called by the registered
# LettA tools). Mounted at the unversioned root and kept out of the public docs.
from app.routers.internal_onboarding import router as internal_onboarding_router  # noqa: E402

app.include_router(internal_onboarding_router, include_in_schema=False)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    if request.url.path in ("/", "/index.html"):  # root HTML must always be fresh, else browsers re-use the old app
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.get("/", include_in_schema=False)
async def index():
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(str(index_file)) if index_file.exists() else JSONResponse(
        {"message": "NOVI API is running. Frontend not found — see /docs for the API."}
    )


@app.get("/api/v1/health", tags=["health"])
async def health():
    from app.services.providers import memory

    return {
        "status": "healthy",
        "service": f"{settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "memory": memory.source(),
    }


@app.get("/.well-known/health")
async def well_known_health():
    return {"status": "ok"}