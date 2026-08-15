"""
ОценитьКвартиру — FastAPI application entry point.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ОценитьКвартиру API",
    description="API для автоматизированной оценки рыночной стоимости квартир",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5000,http://localhost:3000")
cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
def health_check():
    """Service health check — returns 200 when the API is running."""
    return {"status": "ok", "service": "real-estate-analyzer", "version": "1.0.0"}
