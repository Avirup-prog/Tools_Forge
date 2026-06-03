"""
ToolForge — Phase 4 FastAPI Backend
Hosted on Render · https://toolforge-api.onrender.com
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from routers import pdf, image, media, utils


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing heavy needed yet
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="ToolForge API",
    description="Backend for ToolForge — 65 free online tools. PDF, Image, Media, and Utility processing.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow requests from Netlify frontend (and localhost for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://toolsforge.netlify.app",
        "http://localhost:3000",
        "http://127.0.0.1:5500"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(pdf.router,   prefix="/api/pdf",   tags=["PDF"])
app.include_router(image.router, prefix="/api/image", tags=["Image"])
app.include_router(media.router, prefix="/api/media", tags=["Media"])
app.include_router(utils.router, prefix="/api/utils", tags=["Utils"])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "service": "ToolForge API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
