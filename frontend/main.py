"""
FastAPI app that serves both the static HTML frontend and the API backend.
This combines the existing AILA legal analyzer API with static file serving for deployment.
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Add the parent directory to the Python path so we can import aila
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the existing API app
from aila.api.main import app as api_app

# Create the main FastAPI app
app: FastAPI = FastAPI(
    title="AILA - AI Legal Assistant",
    description="AI-powered legal document comparison and analysis with web interface",
    version="1.0.0",
)

# Get the current directory (frontend)
frontend_dir: Path = Path(__file__).parent
static_dir: Path = frontend_dir / "static"

# Mount the existing API under /api prefix
app.mount("/api", api_app)

# Mount static files (CSS, JS, etc.)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Configure TrustedHostMiddleware from environment
trusted_hosts_env = os.getenv("AILA_TRUSTED_HOSTS", "").strip()
if trusted_hosts_env:
    trusted_hosts = [h.strip() for h in trusted_hosts_env.split(",") if h.strip()]
else:
    railway_host = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
    trusted_hosts = []
    if railway_host:
        trusted_hosts.append(railway_host)
    if os.getenv("AILA_ENVIRONMENT", "development") == "development":
        trusted_hosts.extend(["localhost", "127.0.0.1"])
    # If still empty (e.g., prod without envs), allow all but log a note via print
    if not trusted_hosts:
        print("[WARN] No trusted hosts configured; allowing all (*). Set AILA_TRUSTED_HOSTS to lock down.")
        trusted_hosts = ["*"]

app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
print(f"TrustedHostMiddleware configured with hosts: {trusted_hosts}")


@app.get("/", response_model=None)
async def serve_frontend() -> Response:
    html_path = static_dir / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return JSONResponse(
        {"error": "Frontend not found. Please ensure static/index.html exists."},
        status_code=404,
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check for the main app."""
    return {"status": "healthy", "service": "AILA Full Stack", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    port: int = int(os.getenv("PORT", 8000))
    print(f"Starting AILA Full Stack on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
