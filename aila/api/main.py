"""
Legal Document Change Analyzer - Simple FastAPI Backend

A clean, minimal API that directly uses the aila package.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aila.config import get_server_api_keys
from aila.legal_analyzer import AnalysisResult, analyze_documents
from aila.llm_interface import get_llm_interface
from aila.llm_models import LlmConfig, ProviderName
from aila.load_document import load_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# load .env file of root directory (if it exists)
path_env_file = Path(__file__).parent.parent.parent / ".env"
print(f"Loading environment variables from {path_env_file}")

if path_env_file.exists():
    load_dotenv(path_env_file)
    print("Loaded .env file")
else:
    print("No .env file found, using environment variables from system")

SERVER_API_KEYS = get_server_api_keys()

if not any(SERVER_API_KEYS.values()):
    logger.warning("no server side api keys found")


class AnalysisResultWithTexts(AnalysisResult):
    """Extended analysis result that includes the full document texts for frontend display."""

    document1_text: str
    document2_text: str


class AnalyzeTextsRequest(BaseModel):
    doc1_text: str
    doc2_text: str
    name_doc1: str
    name_doc2: str
    llm_config: LlmConfig
    prompt_template: str = "prompt_2.txt"


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# Configuration
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}

# Create FastAPI app
app = FastAPI(
    title="AILA - AI Legal Assistant - Frontend",
    description="AI-powered legal document comparison and analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def check_fallback_to_server_llm_api_key(api_key: str, provider_name: ProviderName) -> str:
    if api_key == "":
        server_key = SERVER_API_KEYS.get(provider_name)
        if server_key:
            api_key = server_key
            print(f"Using server-side API key for {provider_name}")
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key is required")
    return api_key


@app.get("/", response_class=JSONResponse)
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "AI Legal Assistant API",
        "documentation": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="AI Legal Assistant", version="1.0.0")


@app.get("/api-keys-status", response_model=bool)
async def get_api_keys_status() -> bool:
    """Check which API keys are available on the server."""
    return any(key and key.strip() for key in SERVER_API_KEYS.values())


@app.get("/debug/config")
async def debug_config() -> dict[str, str]:
    """Debug endpoint to check configuration."""
    from aila.config import get_config

    config = get_config()
    return {
        "prompt_templates_dir": str(config.prompt_templates_dir),
        "PROMPT_TEMPLATES_DIR_env": os.getenv("PROMPT_TEMPLATES_DIR", "NOT_SET"),
        "current_working_dir": str(Path.cwd()),
    }


@app.post("/analyze", response_model=AnalysisResultWithTexts)
async def analyze_documents_endpoint(
    provider_name: ProviderName,
    model: str,
    temperature: float,
    api_key: str,
    document1: UploadFile = File(..., description="First document to compare"),
    document2: UploadFile = File(..., description="Second document to compare"),
    prompt_template: str = "prompt_2.txt",
) -> AnalysisResultWithTexts:
    """Analyze two documents and return changes."""
    try:
        # Validate file uploads
        if not document1.filename or not document2.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both document files must be provided")

        # Check file extensions
        if not (allowed_file(document1.filename) and allowed_file(document2.filename)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # Check file sizes
        if document1.size and document1.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Document1 is too large. Maximum size is 16MB.",
            )
        if document2.size and document2.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Document2 is too large. Maximum size is 16MB.",
            )

        logger.info(f"Starting analysis: {document1.filename} vs {document2.filename}")

        # Create temporary directory and save files
        temp_dir = Path(tempfile.mkdtemp())
        filepath1 = temp_dir / f"doc1_{document1.filename}"
        filepath2 = temp_dir / f"doc2_{document2.filename}"

        try:
            # Save uploaded files
            with open(filepath1, "wb") as f:
                content = await document1.read()
                f.write(content)

            with open(filepath2, "wb") as f:
                content = await document2.read()
                f.write(content)

            # Load document content
            doc1_text = load_document(filepath1)
            doc2_text = load_document(filepath2)

            # Create LlmConfig from individual parameters
            llm_config = LlmConfig(
                provider_name=provider_name,
                model=model,
                temperature=temperature,
                api_key=api_key,
            )

            # Perform analysis
            llm_interface = get_llm_interface(llm_config)

            result = analyze_documents(
                llm_interface=llm_interface,
                doc1_text=doc1_text,
                doc2_text=doc2_text,
                name_doc1=document1.filename,
                name_doc2=document2.filename,
                prompt_template=prompt_template,
            )

            results_with_parsed_texts = AnalysisResultWithTexts(
                **result.model_dump(),
                document1_text=doc1_text,
                document2_text=doc2_text,
            )

            logger.info("Analysis completed successfully")
            return results_with_parsed_texts

        finally:
            # Clean up temporary files
            if filepath1.exists():
                filepath1.unlink()
            if filepath2.exists():
                filepath2.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze-texts", response_model=AnalysisResult)
async def analyze_texts_endpoint(request: AnalyzeTextsRequest) -> AnalysisResult:
    """Analyze two text documents directly - useful for testing."""
    try:
        logger.info(f"Starting text analysis: {request.name_doc1} vs {request.name_doc2}")

        # Perform analysis
        llm_interface = get_llm_interface(request.llm_config)

        result = analyze_documents(
            llm_interface=llm_interface,
            doc1_text=request.doc1_text,
            doc2_text=request.doc2_text,
            name_doc1=request.name_doc1,
            name_doc2=request.name_doc2,
            prompt_template=request.prompt_template,
        )

        logger.info("Text analysis completed successfully")
        return result

    except Exception as e:
        logger.error(f"Text analysis failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {str(e)}")


# Exception handlers
@app.exception_handler(413)
async def request_entity_too_large_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle file too large error."""
    return JSONResponse(status_code=413, content={"error": "File too large. Maximum size is 16MB."})


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(status_code=404, content={"error": "Endpoint not found"})


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Any) -> JSONResponse:
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(exc)}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting Aila on port {port}")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True, log_level="info")
