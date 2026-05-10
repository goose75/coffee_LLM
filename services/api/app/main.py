"""
Coffee Platform API
===================
FastAPI application entrypoint. Mounts all routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import public, admin, health
from app.api.v1.prices import public_router as prices_public_router, admin_router as prices_admin_router
from app.api.v1.taste import public_router as taste_public_router, admin_router as taste_admin_router
from app.api.v1.assistant import public_router as assistant_public_router, admin_router as assistant_admin_router
from app.api.v1.search import router as search_router
from app.api.v1.compare import router as compare_router
from app.api.v1.origin import router as origin_router
from app.api.v1.roaster_fingerprint import router as fingerprint_router
from app.api.v1.explanations import router as explanations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Coffee Platform API",
    version="0.1.0",
    description="Backend API for the Coffee Intelligence Platform",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(health.router,               tags=["health"])
app.include_router(compare_router,              prefix="/api/v1",       tags=["compare"])
app.include_router(public.router,               prefix="/api/v1",       tags=["public"])
app.include_router(prices_public_router,        prefix="/api/v1",       tags=["prices"])
app.include_router(taste_public_router,         prefix="/api/v1",       tags=["taste"])
app.include_router(assistant_public_router,     prefix="/api/v1",       tags=["assistant"])
app.include_router(admin.router,                prefix="/api/v1/admin", tags=["admin"])
app.include_router(prices_admin_router,         prefix="/api/v1/admin", tags=["admin-prices"])
app.include_router(taste_admin_router,          prefix="/api/v1/admin", tags=["admin-taste"])
app.include_router(assistant_admin_router,      prefix="/api/v1/admin", tags=["admin-assistant"])
app.include_router(search_router, prefix="/api/v1", tags=["search"])
app.include_router(origin_router, prefix="/api/v1", tags=["origins"])
app.include_router(fingerprint_router, prefix="/api/v1", tags=["roasters"])
app.include_router(explanations_router, prefix="/api/v1", tags=["explanations"])
