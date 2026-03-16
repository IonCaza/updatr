from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import activity, auth, credentials, deployment, discovery, hosts, jobs, schedules, compliance, sites, workers
from app.config import settings
from app.database import Base, engine
import app.models  # noqa: F401 — ensures all models are registered with Base.metadata


@asynccontextmanager
async def lifespan(application: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Updatr",
    description="Centralized Patch Management System",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(credentials.router, prefix="/api")
app.include_router(hosts.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(jobs.stream_router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(activity.router, prefix="/api")
app.include_router(sites.router, prefix="/api")
app.include_router(workers.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(deployment.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
