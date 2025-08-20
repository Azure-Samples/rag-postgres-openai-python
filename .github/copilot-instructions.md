# RAG on PostgreSQL - Development Instructions

**ALWAYS FOLLOW THESE INSTRUCTIONS FIRST**. Only search for additional information or use bash commands when the instructions below are incomplete or found to be in error.

## Overview

RAG on PostgreSQL is a Python FastAPI backend with React TypeScript frontend that provides a web-based chat application using OpenAI models to answer questions about data in a PostgreSQL database with pgvector extension. The application is designed for Azure deployment via Azure Developer CLI (azd).

## Required Tools and Dependencies

Install the following tools before beginning development:

- **Python 3.10+** (3.12 recommended)
- **Node.js 18+** for frontend development  
- **PostgreSQL 14+** with pgvector extension
- **Azure Developer CLI (azd)** for deployment
- **Docker Desktop** for dev containers (optional)
- **Git** for version control

## Development Environment Setup

### Bootstrap the Development Environment

Run these commands in sequence. NEVER CANCEL any long-running commands:

1. **Install Python dependencies** (takes ~90 seconds):
   ```bash
   python3 -m pip install -r requirements-dev.txt
   ```

2. **Install backend package in editable mode** (takes ~5 seconds):
   ```bash
   python3 -m pip install -e src/backend
   ```

3. **Install PostgreSQL and pgvector extension**:
   ```bash
   # Ubuntu/Debian:
   sudo apt update && sudo apt install -y postgresql-16-pgvector
   
   # Start PostgreSQL and set password
   sudo service postgresql start
   sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres'"
   ```

4. **Configure environment file**:
   ```bash
   cp .env.sample .env
   ```
   Edit `.env` to set `POSTGRES_USERNAME=postgres` and `POSTGRES_PASSWORD=postgres`.

5. **Set up database and seed data** (takes ~2 seconds each):
   ```bash
   python ./src/backend/fastapi_app/setup_postgres_database.py
   python ./src/backend/fastapi_app/setup_postgres_seeddata.py
   ```

6. **Install frontend dependencies** (takes ~22 seconds):
   ```bash
   cd src/frontend
   npm install
   cd ../../
   ```

7. **Build frontend** (takes ~12 seconds):
   ```bash
   cd src/frontend
   npm run build
   cd ../../
   ```

8. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Running the Application

### Backend Server
```bash
python -m uvicorn fastapi_app:create_app --factory --reload
```
Serves at `http://localhost:8000` with built frontend included.

### Frontend Development Server (with hot reloading)
```bash
cd src/frontend
npm run dev
```
Serves at `http://localhost:5173/` with hot reloading for development.

### Both via VS Code
Use "Frontend & Backend" configuration in the VS Code Run & Debug menu.

## Code Quality and Testing

### Linting and Formatting (ALWAYS run before committing)
```bash
ruff check .          # Lint code (takes <1 second)
ruff format .          # Format code (takes <1 second)  
mypy . --python-version 3.12  # Type check (takes ~42 seconds)
```

**NOTE**: MyPy may show 1 minor import error in `evals/safety_evaluation.py` which is expected and safe to ignore.

### Testing (NEVER CANCEL - full test suite takes ~25 seconds)
```bash
pytest -s -vv --cov --cov-fail-under=85
```

**CRITICAL**: Some tests may fail with database connection issues if using different PostgreSQL credentials. This is expected in fresh environments and does not indicate broken functionality.

### End-to-End Testing with Playwright (NEVER CANCEL - takes 2+ minutes)
```bash
playwright install chromium --with-deps
pytest tests/e2e.py --tracing=retain-on-failure
```

## Build Times and Timeout Requirements

**CRITICAL TIMING INFORMATION** - Set these timeout values and NEVER CANCEL:

- **Dependencies install**: 90 seconds (use 180+ second timeout)
- **Frontend npm install**: 22 seconds (use 60+ second timeout)  
- **Frontend build**: 12 seconds (use 30+ second timeout)
- **MyPy type checking**: 42 seconds (use 90+ second timeout)
- **Full test suite**: 25 seconds (use 60+ second timeout)
- **Playwright E2E tests**: 2+ minutes (use 300+ second timeout)

## Manual Validation After Changes

**ALWAYS perform these validation steps after making code changes:**

1. **Lint and format code**:
   ```bash
   ruff check . && ruff format .
   ```

2. **Type check (if Python changes)**:
   ```bash
   mypy . --python-version 3.12
   ```

3. **Run relevant tests**:
   ```bash
   pytest tests/test_<relevant_module>.py -v
   ```

4. **Test application end-to-end**:
   ```bash
   # Start server
   python -m uvicorn fastapi_app:create_app --factory --reload
   ```
   Then in another terminal:
   ```bash
   # Test API endpoints
   curl http://localhost:8000/items/1
   # Should return JSON with item data
   
   # Test frontend
   curl http://localhost:8000/ | head -n 5
   # Should return HTML with "RAG on PostgreSQL" title
   ```

5. **Test frontend build**:
   ```bash
   cd src/frontend && npm run build
   ```

6. **Functional testing scenarios**:
   - Open `http://localhost:8000/` in browser
   - Verify the "Product chat" interface loads with example questions
   - Click an example question (will show Azure auth error in local dev - this is expected)
   - Verify the frontend UI is responsive and properly styled

## Key Project Structure

### Backend (`src/backend/fastapi_app/`)
- `__init__.py` - FastAPI app factory
- `api_models.py` - Pydantic models for API
- `postgres_engine.py` - Database connection setup
- `postgres_searcher.py` - Vector and text search logic
- `rag_simple.py`, `rag_advanced.py` - RAG implementations
- `routes/api_routes.py` - API endpoints
- `routes/frontend_routes.py` - Static file serving

### Frontend (`src/frontend/`)
- React TypeScript app with FluentUI components
- Vite build system
- Built files output to `src/backend/static/`

### Infrastructure (`infra/`)
- Bicep templates for Azure deployment
- `main.bicep` - Main infrastructure definition

### Configuration Files
- `pyproject.toml` - Python project config (ruff, mypy, pytest)
- `requirements-dev.txt` - Development dependencies
- `azure.yaml` - Azure Developer CLI configuration
- `.env.sample` - Environment variable template

## Azure Deployment

**Deploy to Azure using azd** (NEVER CANCEL - can take 10+ minutes):
```bash
azd auth login
azd env new
azd up
```

**Get deployment values**:
```bash
azd env get-values
```

## OpenAI Configuration Options

The application supports multiple OpenAI providers:

1. **Azure OpenAI** (recommended for production):
   Set `OPENAI_CHAT_HOST=azure` and `OPENAI_EMBED_HOST=azure`

2. **OpenAI.com**:
   Set `OPENAI_CHAT_HOST=openai` and `OPENAI_EMBED_HOST=openai`

3. **Ollama** (local):
   Set `OPENAI_CHAT_HOST=ollama`

4. **GitHub Models**:
   Set `OPENAI_CHAT_HOST=github`

## Common Issues and Solutions

### Database Connection Issues
- Verify PostgreSQL is running: `sudo service postgresql status`
- Check `.env` file has correct `POSTGRES_USERNAME` and `POSTGRES_PASSWORD`
- Ensure pgvector extension is installed: `sudo apt install postgresql-16-pgvector`

### Frontend Build Issues
- Clear npm cache: `cd src/frontend && npm cache clean --force`
- Delete node_modules and reinstall: `rm -rf node_modules && npm install`

### Azure Authentication in Local Development
- Expected behavior: Chat queries will show "Azure Developer CLI could not be found" error
- This is normal for local development without Azure OpenAI configured
- Core application functionality (database, API endpoints, frontend) works correctly
- For full chat functionality, configure Azure OpenAI or use OpenAI.com API key

### CI/CD Pipeline Requirements
The GitHub Actions require:
- Python 3.10+ with specific versions (3.10, 3.11, 3.12)
- PostgreSQL with pgvector extension
- Node.js 18+
- All code passes `ruff check`, `ruff format --check`, and `mypy`

## Load Testing

Use locust for load testing:
```bash
python -m pip install locust  # if not already installed
locust
```
Open `http://localhost:8089/` and point to your running application.

## Available API Endpoints

The application provides these REST API endpoints (view full docs at `http://localhost:8000/docs`):

- `GET /items/{id}` - Get specific item by ID
- `GET /search` - Search items with text query 
- `GET /similar` - Find similar items using vector search
- `POST /chat` - Chat with RAG system (requires OpenAI configuration)
- `POST /chat/stream` - Streaming chat responses

Example API usage:
```bash
# Get item details
curl http://localhost:8000/items/1

# Search for tent-related items (requires OpenAI for embeddings)
curl "http://localhost:8000/search?query=tent&limit=5"
```

## Directory Reference

**Quick ls -la output for repository root:**
```
.devcontainer/          # Dev container configuration
.env.sample            # Environment variables template  
.github/               # GitHub Actions workflows
.gitignore            # Git ignore patterns
.pre-commit-config.yaml # Pre-commit hook configuration
CONTRIBUTING.md       # Contribution guidelines
README.md            # Main project documentation
azure.yaml          # Azure Developer CLI configuration
docs/               # Additional documentation
evals/             # Evaluation scripts
infra/            # Azure infrastructure templates
locustfile.py    # Load testing configuration
pyproject.toml  # Python project configuration
requirements-dev.txt # Development dependencies
scripts/        # Database and deployment scripts
src/           # Source code (backend/ and frontend/)
tests/        # Test suite
```

## Working Effectively

- **Always build and test locally before committing**
- **Use pre-commit hooks** - they run ruff automatically
- **Check the GitHub Actions** in `.github/workflows/` for CI requirements
- **Reference the full README.md** for deployment and Azure-specific details  
- **Use VS Code with the Python and Ruff extensions** for the best development experience
- **Never skip the frontend build** - the backend serves static files from `src/backend/static/`

This project follows modern Python and TypeScript development practices with comprehensive tooling for code quality, testing, and deployment.