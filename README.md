# Aila - AI Legal Assistant

Aila detects changes in legal documents using Anthropic or OpenAI APIs.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/your-username/aila.git
cd aila

# Create virtual environment and setup
python -m venv .venv
cp .env.example .env
# Edit .env with your API keys

# Run setup script
chmod +x init.sh
./setup.sh

# Start API server (FROM PROJECT ROOT!)
python -m uvicorn aila.api.main:app --reload
```

Open http://localhost:8000 for web interface or http://localhost:8000/docs for API docs.

## Usage

### Python Package
```python
from aila.legal_analyzer import analyze_documents
from aila.llm_interface import init_llm_interface
from aila.llm_models import LlmConfig, ProviderName

llm_config = LlmConfig(provider_name=ProviderName.ANTHROPIC, model="claude-3-5-sonnet-20241022")
llm_interface = init_llm_interface(llm_config)
result = analyze_documents(llm_interface, "doc1.pdf", "doc2.pdf", "prompt_1.txt")
```

### REST API
```bash
curl -X POST "http://localhost:8000/analyze?provider_name=anthropic&model=claude-3-5-haiku-20241022" \
  -F "document1=@doc1.pdf" \
  -F "document2=@doc2.pdf"
```

### Web Interface
![Screen Recording](documentation/ui_demo.gif)


## Requirements

- Python 3.12+
- Poetry
- API key from Anthropic or OpenAI

## Docker Deployment

### Quick Start with Docker

```bash
# 1. Make sure you have your .env file with API keys
cp .env.example .env
# Edit .env with your API keys

# 2. Build and run with docker compose
docker compose up --build -d

# Alternative: Build and run with docker directly
docker build -t aila-api .
docker run -d -p 8000:8000 --name aila-api --env-file .env aila-api

# Verify it's running
curl http://localhost:8000/health

# Container management
docker ps                              # View running containers
docker compose logs                    # View logs (compose)
docker compose down                    # Stop and remove containers
docker compose up -d                   # Start containers
# Or for direct docker containers:
# docker logs aila-api                 # View logs
# docker stop aila-api                 # Stop container
# docker start aila-api                # Start container
```

The API will be available at http://localhost:8000

### Production Deployment

For production, consider:
- Using environment variables instead of .env file
- Adding a reverse proxy (nginx example included in docker-compose.yml)
- Setting up SSL certificates
- Using a proper database for logs/results

### Frontend

The frontend is a static HTML file (`frontend/aila.html`) that doesn't need containerization. You can:
- Serve it directly with any web server
- Host it on a CDN or static hosting service
- Include it in your nginx configuration

## Development

```bash
# Quality checks
mypy aila/
ruff check .
ruff format .

# Tests
pytest
```
