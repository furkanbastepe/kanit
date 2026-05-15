from __future__ import annotations

import os
import sys
from pathlib import Path

# Make project root importable so `features.*` resolves on Vercel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Defaults — override via Vercel Environment Variables dashboard
os.environ.setdefault("KANIT_AI_MODE", "nvidia")
os.environ.setdefault("KANIT_ALLOW_MOCK", "true")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from features.main import app as backend_app

# Thin gateway: adds CORS and mounts the real app under /api.
# Vercel routes /api/:path* here; Starlette strips the /api prefix
# before dispatching to backend_app, so existing routes (/health,
# /incidents/analyze, …) match without any changes to features/main.py.
app = FastAPI(title="KANIT Gateway", docs_url=None, redoc_url=None)

# Fix C: Restrict CORS origins via env var. Set KANIT_ALLOWED_ORIGINS to a
# comma-separated list of allowed origins (e.g. "https://kanit.vercel.app").
# Defaults to "*" only when not configured (local dev / demo mode).
_raw_origins = os.getenv("KANIT_ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-KANIT-API-Key"],
)

app.mount("/api", backend_app)
