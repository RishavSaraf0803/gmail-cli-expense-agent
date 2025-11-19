# FinCLI Developer Guide

Complete guide for developers contributing to or understanding FinCLI's architecture.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Design Patterns](#design-patterns)
4. [Testing](#testing)
5. [Development Setup](#development-setup)
6. [Code Quality](#code-quality)
7. [Contributing](#contributing)
8. [Release Process](#release-process)

---

## Architecture Overview

### Layers

```
┌─────────────────────────────────────────┐
│     CLI Layer (cli.py, run_api.py)      │  User interfaces
├─────────────────────────────────────────┤
│     API Layer (fincli/api/)             │  REST API with FastAPI
├─────────────────────────────────────────┤
│  Business Logic (fincli/extractors/)    │  Transaction extraction
├─────────────────────────────────────────┤
│   Data Access (fincli/storage/)         │  Database operations
├─────────────────────────────────────────┤
│  External Clients (fincli/clients/)     │  Gmail, LLM providers
├─────────────────────────────────────────┤
│ Infrastructure (fincli/auth/, utils/)   │  Auth, logging, config
└─────────────────────────────────────────┘
```

### Key Components

#### 1. Configuration (fincli/config.py)
- **Pydantic v2** settings with validation
- Environment variable support (`.env`)
- Type-safe configuration with defaults
- Field validators for complex validation

#### 2. Authentication (fincli/auth/)
- Gmail OAuth2 flow
- Token management and refresh
- Read-only scope (`gmail.readonly`)
- Singleton pattern for service instance

#### 3. LLM Clients (fincli/clients/)
```python
BaseLLMClient (ABC)           # Abstract base class
├── BedrockClient             # AWS Bedrock (Claude)
├── OllamaClient              # Local Ollama models
├── OpenAIClient              # OpenAI GPT models
└── AnthropicClient           # Anthropic Direct API

LLMFactory                    # Factory pattern for creation
LLMRouter                     # Use-case based routing
```

**Key Features:**
- Abstract base class for provider-agnostic code
- Retry logic with exponential backoff (tenacity)
- Health checks for all providers
- JSON extraction with validation

#### 4. Database (fincli/storage/)
- **SQLAlchemy 2.0** ORM
- SQLite for local, PostgreSQL/MySQL ready
- Context manager for sessions
- Indexed columns for performance
- Type hints with `Mapped[]`

#### 5. Transaction Extraction (fincli/extractors/)
- LLM-powered extraction from emails
- Pydantic models for validation
- Date parsing with `dateutil`
- Configurable use-case routing

#### 6. REST API (fincli/api/)
- **FastAPI** framework
- Auto-generated OpenAPI docs
- Pydantic request/response schemas
- Dependency injection pattern
- CORS middleware
- Global exception handling

---

## Project Structure

```
gmail-cli-expense-agent/
├── cli.py                          # CLI entry point (Typer)
├── run_api.py                      # API server launcher
├── setup.py                        # Package configuration
├── requirements.txt                # Production dependencies
├── requirements-dev.txt            # Dev tools (pytest, black, mypy)
├── pytest.ini                      # Pytest configuration
├── .env.example                    # Configuration template
├── .gitignore                      # Git ignore rules
│
├── fincli/                         # Main package
│   ├── __init__.py
│   ├── config.py                   # Pydantic settings
│   │
│   ├── auth/                       # Gmail authentication
│   │   ├── __init__.py
│   │   └── gmail_auth.py           # OAuth2 flow, token management
│   │
│   ├── clients/                    # External API clients
│   │   ├── __init__.py
│   │   ├── base_llm_client.py      # Abstract base class
│   │   ├── bedrock_client.py       # AWS Bedrock implementation
│   │   ├── ollama_client.py        # Ollama local models
│   │   ├── openai_client.py        # OpenAI GPT models
│   │   ├── anthropic_client.py     # Anthropic Direct API
│   │   ├── llm_factory.py          # Factory for client creation
│   │   ├── llm_router.py           # Use-case based routing
│   │   └── gmail_client.py         # Gmail API client
│   │
│   ├── storage/                    # Database layer
│   │   ├── __init__.py
│   │   ├── models.py               # SQLAlchemy models
│   │   └── database.py             # CRUD operations, session management
│   │
│   ├── extractors/                 # Transaction extraction
│   │   ├── __init__.py
│   │   └── transaction_extractor.py # LLM-powered extraction
│   │
│   ├── api/                        # REST API
│   │   ├── __init__.py
│   │   ├── app.py                  # FastAPI application factory
│   │   ├── schemas.py              # Pydantic request/response models
│   │   ├── dependencies.py         # Dependency injection
│   │   └── routers/                # API endpoints
│   │       ├── __init__.py
│   │       ├── transactions.py     # Transaction CRUD
│   │       ├── analytics.py        # Analytics endpoints
│   │       └── operations.py       # Fetch, init, chat
│   │
│   └── utils/                      # Utilities
│       ├── __init__.py
│       └── logger.py               # Structured logging (structlog)
│
└── tests/                          # Test suite
    ├── conftest.py                 # Pytest fixtures
    ├── unit/                       # Unit tests
    │   ├── test_config.py
    │   ├── test_database.py
    │   ├── test_models.py
    │   ├── test_gmail_client.py
    │   ├── test_bedrock_client.py
    │   ├── test_extractor.py
    │   └── test_logger.py
    └── test_api/                   # API integration tests
        ├── conftest.py
        ├── test_transactions.py
        ├── test_analytics.py
        └── test_operations.py
```

---

## Design Patterns

### 1. Singleton Pattern
**Used for:** Database manager, API clients, LLM router

```python
# Example: Database Manager Singleton
_db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
```

### 2. Factory Pattern
**Used for:** LLM client creation

```python
def get_client_by_provider(provider: str) -> BaseLLMClient:
    if provider == "bedrock":
        return get_bedrock_client()
    elif provider == "ollama":
        return get_ollama_client()
    # ...
```

### 3. Strategy Pattern
**Used for:** Retry logic, LLM provider selection

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10)
)
def api_call():
    # Automatic retry with exponential backoff
    pass
```

### 4. Repository Pattern
**Used for:** Database operations abstraction

```python
class DatabaseManager:
    def add_transaction(...) -> Transaction:
        """Abstract database operations"""
        with self.get_session() as session:
            # Implementation hidden from caller
```

### 5. Dependency Injection
**Used for:** FastAPI endpoints

```python
@router.get("/transactions")
async def list_transactions(
    db: DatabaseManager = Depends(get_db_manager),
    gmail: GmailClient = Depends(get_gmail)
):
    # Dependencies injected automatically
```

### 6. Abstract Base Class
**Used for:** LLM provider interface

```python
class BaseLLMClient(ABC):
    @abstractmethod
    def generate_text(...) -> str:
        pass
```

---

## Testing

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated tests
│   ├── test_config.py       # 10 tests - Configuration
│   ├── test_database.py     # 13 tests - Database operations
│   ├── test_models.py       # 6 tests - SQLAlchemy models
│   ├── test_gmail_client.py # 12 tests - Gmail client
│   ├── test_bedrock_client.py # 12 tests - Bedrock client
│   ├── test_extractor.py    # 14 tests - Transaction extractor
│   └── test_logger.py       # 6 tests - Logging
└── test_api/                # Integration tests
    ├── test_transactions.py # Transaction endpoints
    ├── test_analytics.py    # Analytics endpoints
    └── test_operations.py   # Operations endpoints
```

### Running Tests

```bash
# All tests
pytest

# Specific module
pytest tests/unit/test_config.py

# Specific test
pytest tests/unit/test_config.py::TestSettings::test_default_settings

# With coverage
pytest --cov=fincli --cov-report=html

# View coverage
open htmlcov/index.html

# Verbose output
pytest -v

# Only unit tests
pytest tests/unit/

# Watch mode (run on file changes)
pytest-watch
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Run tests that don't require credentials
pytest -m "not requires_credentials"
```

### Writing Tests

#### Example Unit Test

```python
import pytest
from fincli.storage.database import DatabaseManager

class TestDatabaseManager:
    """Test DatabaseManager class."""

    def test_add_transaction(self, db_manager, sample_transaction):
        """Test adding a transaction."""
        result = db_manager.add_transaction(**sample_transaction)

        assert result is not None
        assert result.amount == sample_transaction["amount"]
        assert result.merchant == sample_transaction["merchant"]
```

#### Using Fixtures

```python
def test_with_database(db_manager, sample_transaction):
    """Test using fixtures from conftest.py."""
    transaction = db_manager.add_transaction(**sample_transaction)
    assert transaction is not None
```

#### Mocking External Services

```python
from unittest.mock import MagicMock, patch

@patch('fincli.clients.gmail_client.build')
def test_gmail_client(mock_build):
    """Test Gmail client with mock."""
    mock_build.return_value = MagicMock()
    client = GmailClient()
    assert client is not None
```

### Available Fixtures

**Configuration:**
- `test_settings` - Test settings instance

**Database:**
- `test_db` - In-memory test database
- `db_manager` - Test database manager
- `sample_transaction` - Sample transaction data

**Mocks:**
- `mock_gmail_service` - Mocked Gmail service
- `mock_llm_client` - Mocked LLM client

**Sample Data:**
- `sample_email_data` - Sample email message
- `sample_llm_response` - Sample LLM response

### Coverage Goals

- **Overall:** > 70%
- **Critical modules:** > 80%
  - config.py
  - storage/database.py
  - clients/
  - extractors/

**Current Status:** 73/73 tests passing, 37% coverage

---

## Development Setup

### 1. Install Dev Dependencies

```bash
pip install -r requirements-dev.txt
```

Includes:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking library
- `black` - Code formatter
- `ruff` - Fast linter
- `mypy` - Type checker
- `pre-commit` - Git hooks

### 2. Setup Pre-commit Hooks

```bash
pre-commit install
```

Runs automatically on `git commit`:
- Code formatting (black)
- Linting (ruff)
- Type checking (mypy)
- Trailing whitespace removal
- YAML/JSON validation

### 3. Install in Editable Mode

```bash
pip install -e .
```

Allows importing `fincli` package during development.

---

## Code Quality

### Formatting

```bash
# Format all code
black fincli/ cli.py tests/

# Check without modifying
black --check fincli/
```

**Configuration:** `.black` default (88 char line length)

### Linting

```bash
# Lint all code
ruff check fincli/ cli.py tests/

# Auto-fix issues
ruff check --fix fincli/

# Show statistics
ruff check --statistics fincli/
```

**Configuration:** `pyproject.toml` or `ruff.toml`

### Type Checking

```bash
# Type check all code
mypy fincli/ cli.py

# Strict mode
mypy --strict fincli/
```

**Configuration:** `mypy.ini` or `pyproject.toml`

### All Checks

```bash
# Run all pre-commit hooks
pre-commit run --all-files
```

---

## Contributing

### Workflow

1. **Fork & Clone**
   ```bash
   git clone https://github.com/your-username/fincli.git
   cd fincli
   ```

2. **Create Branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Make Changes**
   - Write code
   - Add tests
   - Update documentation

4. **Run Tests**
   ```bash
   pytest
   pytest --cov=fincli
   ```

5. **Code Quality**
   ```bash
   black fincli/ cli.py
   ruff check --fix fincli/
   mypy fincli/
   ```

6. **Commit**
   ```bash
   git add .
   git commit -m "Add amazing feature"
   ```

7. **Push & PR**
   ```bash
   git push origin feature/amazing-feature
   # Open Pull Request on GitHub
   ```

### Commit Message Guidelines

```
feat: Add OpenAI provider support
fix: Resolve email date parsing issue
docs: Update setup guide for Ollama
test: Add tests for LLM router
refactor: Simplify database session management
chore: Update dependencies
```

### Pull Request Checklist

- [ ] Tests added/updated
- [ ] All tests passing (`pytest`)
- [ ] Code formatted (`black`)
- [ ] Linting passed (`ruff`)
- [ ] Type checking passed (`mypy`)
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)

---

## Release Process

### Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for new features (backwards compatible)
- **PATCH** version for bug fixes

### Release Steps

1. **Update Version**
   - `setup.py`
   - `fincli/__init__.py`
   - `README.md`

2. **Update Changelog**
   - Document all changes
   - Group by type (features, fixes, breaking changes)

3. **Run Full Test Suite**
   ```bash
   pytest --cov=fincli
   black --check fincli/
   ruff check fincli/
   mypy fincli/
   ```

4. **Tag Release**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

5. **Build & Publish** (if applicable)
   ```bash
   python setup.py sdist bdist_wheel
   twine upload dist/*
   ```

---

## Useful Commands

```bash
# Development
pytest                          # Run tests
pytest --cov=fincli            # With coverage
black fincli/                   # Format code
ruff check fincli/              # Lint code
mypy fincli/                    # Type check
pre-commit run --all-files      # All quality checks

# Running locally
python cli.py init              # Initialize
python cli.py fetch             # Fetch transactions
python run_api.py --reload      # Start API with reload

# Database
rm fincli.db                    # Reset database
python cli.py init              # Recreate

# Environment
pip install -r requirements.txt      # Install deps
pip install -r requirements-dev.txt  # Install dev deps
pip install -e .                     # Editable install
```

---

## Architecture Decisions

### Why SQLAlchemy 2.0?
- Modern ORM with full type hints
- Migration support with Alembic
- Works with SQLite, PostgreSQL, MySQL
- Context managers for session management

### Why Pydantic v2?
- Fast validation (written in Rust)
- Type-safe configuration
- Automatic environment variable loading
- JSON schema generation

### Why FastAPI?
- Automatic OpenAPI documentation
- Type hints for validation
- Async support
- Dependency injection
- Fast performance

### Why Typer?
- Type-safe CLI definition
- Auto-generated help
- Integration with Rich for beautiful output
- Modern Python CLI framework

### Why Structlog?
- Structured logging (JSON output)
- Context binding
- Fast performance
- Production-ready

### Why Multiple LLM Providers?
- **Flexibility:** Choose based on cost/quality trade-offs
- **Reliability:** Fallback if one provider is down
- **Optimization:** Best model for each task
- **Cost:** Mix free local and paid cloud models

---

## Performance Considerations

### Database
- Indexed columns for common queries
- Connection pooling
- Batch processing for bulk inserts

### LLM Clients
- Retry logic with exponential backoff
- Timeout configuration
- Connection reuse (keep-alive)

### Gmail API
- Batch message retrieval
- Rate limiting respect
- Incremental sync (skip duplicates)

---

## Security Best Practices

1. **Secrets Management**
   - Never commit `.env` or `credentials.json`
   - Use environment variables for all secrets
   - `.gitignore` includes all sensitive files

2. **Gmail Access**
   - Read-only scope (`gmail.readonly`)
   - OAuth2 with token refresh
   - Credentials stored locally

3. **Database**
   - No hardcoded passwords
   - SQLite file permissions (chmod 600)
   - SQL injection prevention (ORM queries)

4. **API**
   - CORS configuration
   - Input validation (Pydantic)
   - No secrets in responses

---

## Troubleshooting Development Issues

### Import Errors
```bash
# Install in editable mode
pip install -e .
```

### Test Failures
```bash
# Clear pytest cache
pytest --cache-clear

# Verbose output
pytest -vv -s
```

### Type Check Errors
```bash
# Install type stubs
pip install types-requests types-boto3
```

---

## Resources

- **Pytest:** https://docs.pytest.org/
- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Pydantic:** https://docs.pydantic.dev/
- **Typer:** https://typer.tiangolo.com/
- **Black:** https://black.readthedocs.io/
- **Ruff:** https://beta.ruff.rs/docs/

---

**Happy coding! 🚀**
