# FinCLI REST API

A FastAPI-based REST API for the FinCLI expense tracking application. Automatically extract and analyze financial transactions from Gmail using AI.

## Features

- 📧 **Email Integration**: Fetch transaction emails from Gmail
- 🤖 **AI Extraction**: Extract structured transaction data using LLM AI (supports Ollama, Bedrock, OpenAI, Anthropic)
- 💾 **Transaction Management**: CRUD operations for transactions
- 📊 **Analytics**: Financial summaries and merchant insights
- 💬 **Natural Language Q&A**: Ask questions about expenses in plain English
- 📝 **OpenAPI Documentation**: Auto-generated interactive API docs at `/docs`

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file (copy from `.env.example`):

```bash
# Gmail API
FINCLI_GMAIL_CREDENTIALS_PATH=credentials.json
FINCLI_GMAIL_TOKEN_PATH=token.json

# LLM Provider (choose one: ollama, bedrock, openai, anthropic)
FINCLI_LLM_PROVIDER=ollama  # Recommended: free and local!

# Ollama Configuration (if using Ollama)
FINCLI_OLLAMA_BASE_URL=http://localhost:11434
FINCLI_OLLAMA_MODEL_NAME=llama3

# Database
FINCLI_DATABASE_URL=sqlite:///./fincli.db

# API Settings
FINCLI_LOG_LEVEL=INFO
```

### 3. Initialize the Application

```bash
# Create database tables and test connections
curl -X POST http://localhost:8000/init
```

### 4. Run the API Server

```bash
# Development mode with auto-reload
python run_api.py --reload

# Production mode
python run_api.py --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: `http://localhost:8000`
- Interactive Docs (Swagger UI): `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI Schema: `http://localhost:8000/openapi.json`

## API Endpoints

### Root & Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check for all services |

### Transactions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/transactions` | List transactions (with pagination & filters) |
| GET | `/api/v1/transactions/{id}` | Get transaction by ID |
| GET | `/api/v1/transactions/email/{email_id}` | Get transaction by Gmail message ID |
| POST | `/api/v1/transactions` | Create new transaction |

**Query Parameters for GET /api/v1/transactions:**
- `limit` (int, 1-100): Number of items per page (default: 10)
- `offset` (int): Number of items to skip (default: 0)
- `transaction_type` (string): Filter by "debit" or "credit"
- `merchant` (string): Fuzzy search by merchant name
- `start_date` (datetime): Filter by start date (inclusive)
- `end_date` (datetime): Filter by end date (inclusive)

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/summary` | Get financial summary |
| GET | `/api/v1/analytics/merchants/top` | Get top merchants |

**Query Parameters for GET /api/v1/analytics/merchants/top:**
- `limit` (int, 1-100): Number of merchants (default: 10)
- `transaction_type` (string): Filter by "debit" or "credit"

### Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/init` | Initialize database and test connections |
| POST | `/fetch` | Fetch emails and extract transactions |
| POST | `/chat` | Ask natural language questions |

## Usage Examples

### 1. Fetch Transactions from Gmail

```bash
curl -X POST "http://localhost:8000/fetch" \
  -H "Content-Type: application/json" \
  -d '{
    "max_emails": 50,
    "force": false
  }'
```

Response:
```json
{
  "new_transactions": 15,
  "skipped_duplicates": 10,
  "errors": 0,
  "total_in_db": 25
}
```

### 2. List Transactions

```bash
# Get first 10 transactions
curl "http://localhost:8000/api/v1/transactions"

# Get transactions with pagination
curl "http://localhost:8000/api/v1/transactions?limit=20&offset=10"

# Filter by type
curl "http://localhost:8000/api/v1/transactions?transaction_type=debit"

# Search by merchant
curl "http://localhost:8000/api/v1/transactions?merchant=Amazon"

# Filter by date range
curl "http://localhost:8000/api/v1/transactions?start_date=2025-01-01T00:00:00&end_date=2025-12-31T23:59:59"
```

Response:
```json
{
  "items": [
    {
      "id": 1,
      "email_id": "msg_abc123",
      "amount": 1250.50,
      "transaction_type": "debit",
      "merchant": "Amazon",
      "currency": "INR",
      "transaction_date": "2025-11-15T10:30:00",
      "email_subject": "Transaction Alert",
      "created_at": "2025-11-15T10:35:00",
      "updated_at": "2025-11-15T10:35:00"
    }
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

### 3. Get Financial Summary

```bash
curl "http://localhost:8000/api/v1/analytics/summary"
```

Response:
```json
{
  "total_spent": 15750.50,
  "total_credited": 5000.00,
  "net": -10750.50,
  "total_transactions": 25,
  "currency": "INR"
}
```

### 4. Get Top Merchants

```bash
curl "http://localhost:8000/api/v1/analytics/merchants/top?limit=5&transaction_type=debit"
```

Response:
```json
{
  "merchants": [
    {
      "merchant": "Amazon",
      "transaction_count": 8,
      "total_amount": 5200.00
    },
    {
      "merchant": "Swiggy",
      "transaction_count": 12,
      "total_amount": 3450.00
    }
  ],
  "transaction_type": "debit"
}
```

### 5. Create Transaction Manually

```bash
curl -X POST "http://localhost:8000/api/v1/transactions" \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "manual_entry_001",
    "amount": 500.00,
    "transaction_type": "debit",
    "merchant": "Local Store",
    "transaction_date": "2025-11-20T14:30:00",
    "currency": "INR",
    "notes": "Cash purchase entered manually"
  }'
```

### 6. Ask Natural Language Questions

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How much did I spend on food delivery last month?"
  }'
```

Response:
```json
{
  "question": "How much did I spend on food delivery last month?",
  "answer": "Based on your transactions, you spent INR 4,250 on food delivery services in the last month. This includes 12 transactions from Swiggy (INR 2,800) and 5 transactions from Zomato (INR 1,450).",
  "conversation_id": "uuid-1234-5678",
  "timestamp": "2025-11-20T15:45:00"
}
```

## Request/Response Models

### TransactionCreate

```json
{
  "email_id": "string",
  "amount": 0.0,
  "transaction_type": "debit|credit",
  "merchant": "string",
  "transaction_date": "2025-11-20T10:30:00",
  "currency": "INR",
  "email_subject": "string (optional)",
  "email_snippet": "string (optional)",
  "category": "string (optional)",
  "notes": "string (optional)"
}
```

### TransactionResponse

```json
{
  "id": 1,
  "email_id": "string",
  "amount": 0.0,
  "transaction_type": "debit|credit",
  "merchant": "string",
  "currency": "INR",
  "transaction_date": "2025-11-20T10:30:00",
  "email_subject": "string",
  "email_snippet": "string",
  "email_date": "2025-11-20T10:25:00",
  "category": "string",
  "notes": "string",
  "created_at": "2025-11-20T10:30:00",
  "updated_at": "2025-11-20T10:30:00"
}
```

## Error Handling

The API uses standard HTTP status codes:

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource already exists (duplicate)
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: External service unavailable

Error Response Format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Running Tests

```bash
# Run all API tests
pytest tests/test_api/ -v

# Run with coverage
pytest tests/test_api/ --cov=fincli.api --cov-report=html

# Run specific test file
pytest tests/test_api/test_transactions.py -v
```

## Architecture

```
fincli/
├── api/
│   ├── __init__.py
│   ├── app.py              # FastAPI application factory
│   ├── schemas.py          # Pydantic request/response models
│   ├── dependencies.py     # Dependency injection
│   └── routers/
│       ├── __init__.py
│       ├── transactions.py # Transaction endpoints
│       ├── analytics.py    # Analytics endpoints
│       └── operations.py   # Operations endpoints
├── clients/                # External API clients
├── extractors/             # AI extraction logic
├── storage/                # Database models & operations
└── utils/                  # Utilities (logging, etc.)
```

## Development

### Running in Development Mode

```bash
# With auto-reload
python run_api.py --reload --log-level debug

# Using uvicorn directly
uvicorn fincli.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Environment Variables

See `.env.example` for all available configuration options.

Key settings:
- `FINCLI_DEBUG`: Enable debug mode (default: False)
- `FINCLI_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `FINCLI_LOG_FORMAT`: Log format (console, json)
- `FINCLI_DATABASE_URL`: Database connection string
- `FINCLI_LLM_PROVIDER`: LLM provider (ollama, bedrock, openai, anthropic)
- `FINCLI_EMAIL_QUERY`: Gmail search query filter

## Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_api.py", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t fincli-api .
docker run -p 8000:8000 --env-file .env fincli-api
```

### Using Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./fincli.db:/app/fincli.db
      - ./credentials.json:/app/credentials.json
      - ./token.json:/app/token.json
```

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/fincli/issues
- Documentation: http://localhost:8000/docs
