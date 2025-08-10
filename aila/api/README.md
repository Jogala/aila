# aila API

FastAPI backend service for the aila legal document analyzer.

## Overview

This API provides REST endpoints for analyzing legal documents and comparing changes between document versions. It uses the core `aila` library for document processing and LLM-powered analysis.

## Setup
Activate the virtual environment on the root directory:

```bash
cd api
poetry install
```

1. GO BACK TO THE ROOT DIRECTORY, and run the API server:
```bash
poetry run uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
- `GET /api/health` - Service health status

### Document Analysis
- `POST /api/analyze` - Upload and analyze two documents
- `GET /api/demo` - Run demo analysis with sample documents
- `GET /api/analysis/{analysis_id}` - Retrieve analysis results
- `GET /api/export/{analysis_id}/{format}` - Export results (json, txt, html)

### Documentation
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Usage Example

```bash
# Upload documents for analysis
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: multipart/form-data" \
  -F "document1=@contract_v1.pdf" \
  -F "document2=@contract_v2.pdf"

# Run demo analysis
curl "http://localhost:8000/api/demo"

# Export results
curl "http://localhost:8000/api/export/{analysis_id}/json" -o results.json
```

## Configuration

The API can be configured via environment variables:

- `DEFAULT_LLM_PROVIDER` - LLM provider to use (anthropic/openai)
- `ANTHROPIC_API_KEY` - Anthropic API key
- `OPENAI_API_KEY` - OpenAI API key
- `PORT` - Server port (default: 8000)

## Architecture

The API is structured as a clean adapter layer over the core `aila` library:

- `api/main.py` - FastAPI application and route definitions
- `api/pyproject.toml` - API-specific dependencies
- Core logic remains in the `aila/` package

This separation allows the core library to be used independently (CLI, scripts) while providing a web service interface.
