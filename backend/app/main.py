"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import AsyncSessionLocal
from app.routers import ingest, roi, stream
from app.services.connection_limiter import ConnectionLimiter
from app.services.detector import FaceDetector
from app.services.frame_bus import FrameBus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.session_factory = AsyncSessionLocal
    app.state.detector = FaceDetector(settings.detection_confidence)
    app.state.frame_bus = FrameBus()
    app.state.connection_limiter = ConnectionLimiter(settings.max_ws_connections_per_ip)
    logger.info("Backend started (detector + frame bus initialised)")
    yield
    app.state.detector.close()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="MegaAI Face Detection API",
    description="Real-time face ROI detection over WebSocket ingest.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(ingest.router)
app.include_router(stream.router)
app.include_router(roi.router, prefix="/api")
