"""
FastAPI Web Admin Panel — Main Application
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure project root is in path so we can import database/, services/, config
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web.api.auth_routes import router as auth_router
from web.api.courses import router as courses_router
from web.api.lessons import router as lessons_router
from web.api.users import router as users_router
from web.api.stats import router as stats_router
from web.api.upload import router as upload_router
from web.api.registration_fields import router as regfields_router
from web.api.media import router as media_router
from web.api.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    from database import init_db
    await init_db()
    yield


app = FastAPI(
    title="Course Bot Admin Panel",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(stats_router, prefix="/api/stats", tags=["Stats"])
app.include_router(courses_router, prefix="/api/courses", tags=["Courses"])
app.include_router(lessons_router, prefix="/api/lessons", tags=["Lessons"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(upload_router, prefix="/api/upload", tags=["Upload"])
app.include_router(regfields_router, prefix="/api/registration-fields", tags=["Registration Fields"])
app.include_router(media_router, prefix="/api/media", tags=["Media Library"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])

# Serve React frontend (built files)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React SPA — all non-API routes go to index.html."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
