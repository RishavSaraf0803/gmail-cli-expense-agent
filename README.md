
# FinCLI: AI-Powered Gmail Expense Tracker

**Transform your transaction emails into actionable insights using AI.**

A production-ready Python application that connects to Gmail, extracts financial transactions using AI, and provides both a CLI and REST API for expense management and analysis.

[![Tests](https://img.shields.io/badge/tests-73%2F73_passing-success)]() [![Python](https://img.shields.io/badge/python-3.8%2B-blue)]() [![License](https://img.shields.io/badge/license-MIT-green)]() [![Coverage](https://img.shields.io/badge/coverage-38%25-yellow)]()

> **Branch: `feature/rag`** — Adds hybrid RAG (Retrieval-Augmented Generation) for semantic transaction search. See [What's New](#-whats-new-featurerag) below.

---

## ⚡ Quick Start

```bash
# 1. Setup environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure (copy and edit .env file)
cp .env.example .env
# Add your Gmail credentials, choose LLM provider, generate API key

# 3. Generate API key (for REST API security)
python -c "import secrets; print(secrets.token_hex(32))"
# Add to .env: FINCLI_API_KEY=<generated-key>

# 4. Initialize database
python cli.py init

# 5. Start tracking
python cli.py fetch --max 20

# 6. Build RAG search index (new in this branch)
ollama pull nomic-embed-text
python cli.py index

# 7. Chat with semantic search
python cli.py chat
```

**First time?** → See **[SETUP_GUIDE.md](docs/guides/SETUP_GUIDE.md)** for detailed setup instructions.

---

## 🌟 Features

### Core Capabilities
- 📧 **Gmail Integration** - Secure OAuth2, read-only access
- 🤖 **AI Extraction** - Parse transactions from emails automatically
- 💬 **Natural Language Chat** - Ask questions about your spending
- 🔍 **Semantic Search (RAG)** - Find transactions by meaning, not just keywords
- 📊 **Analytics** - Spending summaries, top merchants, trends
- 🌐 **REST API** - Programmatic access with FastAPI
- 💾 **Local Storage** - SQLite database, your data stays with you

### Production Features 🚀
- 🔐 **API Authentication** - API key-based auth with constant-time comparison
- 🛡️ **Rate Limiting** - Token bucket algorithm (100 req/min, 1000 req/hour)
- 🔄 **Circuit Breaker** - Prevents cascading LLM failures
- 🚨 **Fail-Fast Validation** - Won't start if critical dependencies unavailable
- 📈 **Health Endpoints** - `/health`, `/ready`, `/startup`, `/circuit-breakers`
- 🎯 **Structured Errors** - Custom exception hierarchy, proper HTTP codes

### Cost Optimization & Observability
- 🚀 **LLM Response Caching** - 30-90% cost reduction
- 📊 **Metrics Tracking** - Costs, tokens, latency, success rates
- 📝 **Prompt Versioning** - YAML-based prompt management with A/B testing

### Flexible LLM Support
Choose the AI provider that fits your needs:

| Provider | Cost | Setup | Best For |
|----------|------|-------|----------|
| **Ollama** | Free | 5 min | Development, privacy ⭐ |
| **Anthropic Claude** | ~$0.003/1K | 2 min | Best extraction quality |
| **OpenAI GPT** | ~$0.03/1K | 2 min | Best conversations |
| **AWS Bedrock** | Low | 10 min | Enterprise deployments |

**Smart Routing:** Use different providers for different tasks (e.g., free Ollama for chat, paid Claude for extraction).

**Embedding Model:** `nomic-embed-text` via Ollama (free, local, 768-dim vectors) for RAG indexing.

---

## 📚 Documentation

**📂 [Browse all docs](docs/)** - Organized by guides/, technical/, and learning/

### Quick Access
| Guide | Purpose |
|-------|---------|
| **[SETUP_GUIDE.md](docs/guides/SETUP_GUIDE.md)** | Complete installation & configuration |
| **[API_GUIDE.md](docs/guides/API_GUIDE.md)** | REST API documentation |
| **[DEVELOPER_GUIDE.md](docs/guides/DEVELOPER_GUIDE.md)** | Architecture, testing, contributing |
| **[CACHING_GUIDE.md](docs/technical/CACHING_GUIDE.md)** | LLM response caching for cost optimization |
| **[AI_ENGINEERING_GUIDE.md](docs/technical/AI_ENGINEERING_GUIDE.md)** | AI engineering best practices & patterns |
| **[Learning Materials](docs/learning/)** | 12-week AI engineering learning path |
| **[.env.example](.env.example)** | Configuration reference |

---

## 🔒 Security & Production Readiness

### Authentication & Authorization
```bash
# API key authentication (required for production)
FINCLI_API_AUTH_ENABLED=true
FINCLI_API_KEY=<your-64-char-hex-key>

# All API endpoints require X-API-Key header
curl -H "X-API-Key: abc123..." http://localhost:8000/api/v1/transactions
```

### Rate Limiting
Prevents API abuse with token bucket algorithm:
- **100 requests/minute** per API key
- **1000 requests/hour** per API key
- Different costs per endpoint:
  - `/fetch` = 10 tokens (expensive: Gmail + LLM)
  - `/chat` = 5 tokens (moderate: LLM)
  - `/transactions` = 1 token (cheap: DB only)

### Circuit Breaker
Prevents cascading failures when LLM providers go down:
- **5 failures** → Circuit opens (reject calls immediately)
- **60 second timeout** → Try again (half-open state)
- **2 successes** → Circuit closes (resume normal operation)

Monitor at: `GET /circuit-breakers`

### Error Handling
- **Fail-fast startup** - Won't start if DB unreachable or config invalid
- **Custom exceptions** - Proper error categorization (critical vs recoverable)
- **Structured logging** - JSON logs with context
- **Safe error messages** - Full details in dev, safe messages in production

---

## 💻 Usage Examples

### CLI Commands

```bash
# Initialize database and test connections
python cli.py init

# Fetch and process emails
python cli.py fetch --max 50

# Build RAG search index (run after fetch)
python cli.py index

# Force re-embed all transactions (use after changing embedding model)
python cli.py index --reindex

# View spending summary
python cli.py summarize

# List recent transactions
python cli.py list-transactions --limit 20

# Interactive chat (RAG-powered semantic search)
python cli.py chat
> "food delivery transactions"
> "unusual charges last month"
> "anything related to my travel"
> "subscriptions and streaming"
```

### REST API

```bash
# Start API server
python run_api.py

# Health checks (no auth required)
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/circuit-breakers

# API endpoints (auth required)
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/transactions
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/analytics/summary

# Interactive documentation
open http://localhost:8000/docs
```

**API Endpoints:**

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /health` | ❌ No | Liveness check |
| `GET /ready` | ❌ No | Readiness check (DB + LLM) |
| `GET /startup` | ❌ No | Startup completion check |
| `GET /circuit-breakers` | ❌ No | Circuit breaker status |
| `POST /fetch` | ✅ Yes | Fetch and process emails (10 tokens) |
| `GET /api/v1/transactions` | ✅ Yes | List transactions (1 token) |
| `GET /api/v1/analytics/summary` | ✅ Yes | Financial summary (2 tokens) |
| `POST /chat` | ✅ Yes | Natural language Q&A (5 tokens) |

See **[API_GUIDE.md](docs/guides/API_GUIDE.md)** for complete API documentation.

---

## 🎯 Use Cases

### Example 1: Zero Cost Setup (Development)
```bash
# Install Ollama (free, local LLM)
brew install ollama
ollama pull llama3

# Configure FinCLI
echo "FINCLI_LLM_PROVIDER=ollama" >> .env
echo "FINCLI_OLLAMA_MODEL_NAME=llama3" >> .env
echo "FINCLI_API_AUTH_ENABLED=false" >> .env  # Disable auth for dev
```

### Example 2: Best Quality (Production)
```bash
# Use Anthropic Claude for extraction
echo "FINCLI_LLM_PROVIDER=anthropic" >> .env
echo "FINCLI_ANTHROPIC_API_KEY=sk-ant-..." >> .env
echo "FINCLI_API_AUTH_ENABLED=true" >> .env
echo "FINCLI_API_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
```

### Example 3: Hybrid (Cost Optimized)
```bash
# Free Ollama for most tasks, paid Claude only for extraction
echo "FINCLI_LLM_PROVIDER=ollama" >> .env
echo "FINCLI_LLM_EXTRACTION_PROVIDER=anthropic" >> .env
echo "FINCLI_ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│  CLI / REST API                          │  User Interfaces
├──────────────────────────────────────────┤
│  Middleware Layer                        │  Security & Resilience
│  ├─ API Authentication                   │
│  ├─ Rate Limiting (Token Bucket)         │
│  └─ Error Handlers                       │
├──────────────────────────────────────────┤
│  Business Logic                          │  Application Layer
│  ├─ Transaction Extraction               │
│  ├─ RAG Chat (Hybrid Retrieval)          │  ← new
│  └─ Analytics                            │
├──────────────────────────────────────────┤
│  RAG Layer                               │  Semantic Search  ← new
│  ├─ Embedder (nomic-embed-text)          │
│  ├─ Vector Store (numpy cosine sim)      │
│  ├─ Hybrid Retriever (SQL + vectors)     │
│  └─ Indexer (offline embedding pipeline) │
├──────────────────────────────────────────┤
│  Resilience Patterns                     │  Reliability Layer
│  ├─ Circuit Breaker (LLM)                │
│  ├─ Retry with Backoff                   │
│  └─ Fail-Fast Validation                 │
├──────────────────────────────────────────┤
│  Observability & Caching                 │  Monitoring Layer
│  ├─ Metrics Tracking                     │
│  ├─ Structured Logging                   │
│  └─ LLM Response Cache                   │
├──────────────────────────────────────────┤
│  Data & Integration                      │  Infrastructure Layer
│  ├─ Database (SQLite + embeddings table) │  ← updated
│  ├─ LLM Clients (4 providers)            │
│  └─ Gmail Client                         │
└──────────────────────────────────────────┘
```

### RAG Query Flow
```
User question
      │
      ▼
  embed question          ← nomic-embed-text via Ollama
      │
      ▼
  SQL pre-filter          ← extract date/type/amount from query
  (fast, exact)
      │
      ▼
  cosine similarity       ← rank filtered candidates by semantic similarity
  on filtered set
      │
      ▼
  top-K transactions      ← passed as context to LLM
      │
      ▼
  LLM answer              ← grounded in relevant transactions only
```

**Technology Stack:**
- **CLI:** Typer + Rich (beautiful terminal UI)
- **API:** FastAPI (auto-generated docs, async-ready)
- **Database:** SQLAlchemy 2.0 + SQLite
- **AI:** Multi-provider (Ollama, Bedrock, OpenAI, Anthropic)
- **Config:** Pydantic v2 (type-safe, validated)
- **Logging:** Structlog (structured, JSON)
- **Testing:** Pytest (73/73 tests passing)
- **Security:** API keys, rate limiting, circuit breakers

---

## 🔒 Security & Privacy

- ✅ **API Key Authentication** - Constant-time comparison, configurable
- ✅ **Rate Limiting** - Per-key token bucket algorithm
- ✅ **Read-only Gmail access** (`gmail.readonly` scope)
- ✅ **Local data storage** (no cloud sync)
- ✅ **Credentials never committed** (`.gitignore`)
- ✅ **Environment-based secrets** (`.env` file)
- ✅ **Safe error messages** - No sensitive data in production errors
- ✅ **No data sharing** with AI providers (local Ollama option available)

---

## 🧪 Testing

```bash
# Run all tests
bash scripts/run_tests.sh

# Run with coverage
bash scripts/run_tests.sh coverage

# Run only unit tests
bash scripts/run_tests.sh unit

# Clean test artifacts
bash scripts/run_tests.sh clean
```

**Current Status:** ✅ 73/73 tests passing (100% pass rate) | 📊 38% coverage

See **[DEVELOPER_GUIDE.md](docs/guides/DEVELOPER_GUIDE.md#testing)** for testing documentation.

---

## 📊 Project Status

- **Version:** 1.0.0
- **Status:** ✅ Production Ready (Single Instance)
- **Tests:** ✅ 73/73 passing
- **Coverage:** 38%
- **Python:** 3.8+
- **License:** MIT

### Production Readiness

| Feature | Status | Notes |
|---------|--------|-------|
| Authentication | ✅ Ready | API key-based |
| Rate Limiting | ✅ Ready | Token bucket, per-key |
| Circuit Breaker | ✅ Ready | Per-provider tracking |
| Health Checks | ✅ Ready | Liveness, readiness, startup |
| Error Handling | ✅ Ready | Fail-fast, structured errors |
| Observability | ✅ Ready | Metrics, logs, tracing |
| Horizontal Scaling | ⚠️ Limited | Single instance only (SQLite) |
| Background Jobs | ⚠️ Limited | Synchronous processing |

**Suitable for:**
- ✅ Development and staging environments
- ✅ Small production deployments (< 100 req/min)
- ✅ Single-instance deployments
- ✅ Learning and portfolio projects

**Not suitable for:**
- ❌ High-traffic production (> 100 req/min)
- ❌ Multi-instance deployments (needs Redis for rate limiter)
- ❌ Background job processing (needs Celery/Redis)

---

## 🆕 What's New: `feature/rag`

### Hybrid RAG System for Semantic Transaction Search

The `chat` command now uses **Retrieval-Augmented Generation** instead of dumping the last 50 transactions as context. Each question retrieves only the most relevant transactions — faster, more accurate, and cheaper (fewer tokens).

**New command:**
```bash
python cli.py index          # embed all transactions (run after fetch)
python cli.py index --reindex  # force re-embed everything
```

**How it works:**
- Transactions are embedded offline using `nomic-embed-text` (free, local via Ollama)
- Each transaction's email subject + snippet + structured fields are combined into rich text before embedding — real Gmail emails contain prose like *"Your Swiggy order of Butter Chicken has been placed"* which gives the model semantic signal
- At query time: SQL pre-filters by date/type/amount, then cosine similarity re-ranks the filtered set, top-8 results go to the LLM

**New files:**
```
fincli/rag/
  embedder.py      — text → float32 vector via Ollama
  vector_store.py  — store/search vectors (numpy cosine similarity on SQLite BLOBs)
  retriever.py     — hybrid retrieval: SQL pre-filter + vector ranking
  indexer.py       — offline indexing pipeline (incremental + full reindex)
```

**New DB table:** `transaction_embeddings` (1:1 with transactions, stores embedding vector + source text + model name)

**New config:**
```bash
FINCLI_OLLAMA_EMBED_MODEL=nomic-embed-text  # default
```

**Key AI engineering concepts demonstrated:**
- Embeddings and vector similarity (cosine similarity)
- Offline vs online indexing
- Hybrid retrieval (SQL metadata filter + semantic ranking)
- Why RAG works on unstructured text but needs hybrid approach for structured data
- Top-K context window sizing

---

## 🆕 Recent Updates (v1.0.0)

### Production Features (NEW)
- ✅ **API Authentication** - API key validation with constant-time comparison
- ✅ **Rate Limiting** - Token bucket algorithm per API key
- ✅ **Circuit Breaker** - Prevents cascading LLM failures
- ✅ **Fail-Fast Validation** - Startup checks for DB, config, LLM
- ✅ **Health Endpoints** - `/health`, `/ready`, `/startup`, `/circuit-breakers`
- ✅ **Custom Exceptions** - Structured error hierarchy
- ✅ **Safe Error Messages** - Dev vs production error handling

### Core Features
- ✅ Multi-provider LLM support (4 providers)
- ✅ REST API with FastAPI
- ✅ Email date parsing improvements
- ✅ Pydantic v2 compatibility
- ✅ Test suite (73/73 tests passing)
- ✅ Comprehensive documentation

### Cost Optimization & Engineering
- ✅ LLM response caching system (30-90% cost reduction)
- ✅ Observability & metrics tracking (costs, tokens, latency)
- ✅ Prompt versioning with YAML management
- ✅ Cache statistics and performance monitoring
- ✅ Example scripts (`cache_demo.py`, `observability_demo.py`)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Read **[DEVELOPER_GUIDE.md](docs/guides/DEVELOPER_GUIDE.md)** for architecture & setup
2. Fork the repository
3. Create a feature branch
4. Add tests for new features
5. Ensure all tests pass (`bash scripts/run_tests.sh`)
6. Run code quality checks (`black`, `ruff`, `mypy`)
7. Submit a pull request

See **[DEVELOPER_GUIDE.md](docs/guides/DEVELOPER_GUIDE.md#contributing)** for detailed guidelines.

---

## 📖 Documentation Quick Links

**📂 [Browse all docs](docs/)** - Now organized into guides/, technical/, and learning/

- **Getting Started:** [SETUP_GUIDE.md](docs/guides/SETUP_GUIDE.md)
- **API Reference:** [API_GUIDE.md](docs/guides/API_GUIDE.md)
- **Development:** [DEVELOPER_GUIDE.md](docs/guides/DEVELOPER_GUIDE.md)
- **Cost Optimization:** [CACHING_GUIDE.md](docs/technical/CACHING_GUIDE.md)
- **AI Engineering:** [AI_ENGINEERING_GUIDE.md](docs/technical/AI_ENGINEERING_GUIDE.md)
- **Learning Path:** [12-week AI engineering roadmap](docs/learning/)
- **Configuration:** [.env.example](.env.example)
- **Examples:** [examples/](examples/)

---

## 🎓 Learning Resources

This project includes comprehensive AI engineering learning materials:

- 📖 **[Learning Path](docs/learning/LEARNING_PATH.md)** - 12-week structured roadmap
- 🧠 **[AI Concepts Guide](docs/learning/AI_CONCEPTS_GUIDE.md)** - Core concepts explained
- 💻 **[Hands-On Exercises](docs/learning/HANDS_ON_EXERCISES.md)** - 5 coding exercises with solutions
- 🏗️ **[Architecture Diagrams](docs/learning/ARCHITECTURE_DIAGRAMS.md)** - Visual system design
- ⚡ **[Quick Reference](docs/learning/QUICK_REFERENCE.md)** - Code snippets & patterns

Perfect for learning AI engineering by building a real project!

---

## 🚀 What Makes This Project Special?

### For Developers
- ✅ **Production patterns** - Auth, rate limiting, circuit breakers
- ✅ **Multi-provider LLM** - Abstract interface, easy to add providers
- ✅ **Cost optimization** - Caching, metrics, smart routing
- ✅ **Clean architecture** - Layered design, dependency injection
- ✅ **Comprehensive docs** - Setup, API, architecture, learning path

### For AI Engineers
- ✅ **Real-world patterns** - Circuit breakers, fail-fast, observability
- ✅ **LLM best practices** - Prompt versioning, caching, retry logic
- ✅ **Learning materials** - 12-week roadmap, exercises, concepts
- ✅ **Portfolio ready** - Production features, clean code, good docs

### For Learners
- ✅ **Hands-on learning** - Build while you learn
- ✅ **Progressive complexity** - Start simple, add advanced features
- ✅ **Practical examples** - Real transaction extraction use case
- ✅ **Guided path** - 12-week structured learning journey

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit
- [Anthropic Claude](https://www.anthropic.com/) - AI language model
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Structlog](https://www.structlog.org/) - Structured logging

---

**Last Updated:** April 2026 | **Version:** 1.1.0-rag

**Ready to start?** Follow the [Quick Start](#-quick-start) guide above!
