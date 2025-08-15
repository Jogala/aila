"""
FastAPI app that serves both the static HTML frontend and the API backend.
This combines the existing AILA legal analyzer API with static file serving for deployment.
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add the parent directory to the Python path so we can import aila
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the existing API app
from aila.api.main import app as api_app

# Create the main FastAPI app
app: FastAPI = FastAPI(
    title="AILA - AI Legal Assistant",
    description="AI-powered legal document comparison and analysis with web interface",
    version="1.0.0"
)

# Get the current directory (frontend)
frontend_dir: Path = Path(__file__).parent
static_dir: Path = frontend_dir / "static"

# Mount the existing API under /api prefix
app.mount("/api", api_app)

# Mount static files (CSS, JS, etc.)
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_frontend() -> FileResponse | dict[str, str]:
    """Serve the main HTML frontend at the root path."""
    html_path = static_dir / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    else:
        return {"error": "Frontend not found. Please ensure static/index.html exists."}

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check for the main app."""
    return {"status": "healthy", "service": "AILA Full Stack", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    port: int = int(os.getenv("PORT", 8000))
    print(f"Starting AILA Full Stack on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)