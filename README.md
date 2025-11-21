# FinCLI: AI-Powered Gmail Expense Tracker

**Transform your transaction emails into actionable insights using AI.**

A production-ready Python application that connects to Gmail, extracts financial transactions using AI, and provides both a CLI and REST API for expense management and analysis.

[![Tests](https://img.shields.io/badge/tests-106%2F106_passing-success)]() [![Python](https://img.shields.io/badge/python-3.8%2B-blue)]() [![License](https://img.shields.io/badge/license-MIT-green)]()

---

## ⚡ Quick Start

```bash
# 1. Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure (.env file)
cp .env.example .env
# Add your Gmail credentials and choose an LLM provider

# 3. Initialize
python cli.py init

# 4. Start tracking
python cli.py fetch --max 20
python cli.py chat
```

**First time?** → See **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** for detailed setup instructions.

---

## 🌟 Features

### Core Capabilities
- 📧 **Gmail Integration** - Secure OAuth2, read-only access
- 🤖 **AI Extraction** - Parse transactions from emails automatically
- 💬 **Natural Language Chat** - Ask questions about your spending
- 📊 **Analytics** - Spending summaries, top merchants, trends
- 🌐 **REST API** - Programmatic access with FastAPI
- 💾 **Local Storage** - SQLite database, your data stays with you
- 🚀 **LLM Caching** - 30-90% cost reduction via intelligent response caching
- 📈 **Observability** - Track costs, tokens, latency, and success rates
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

---

## 📚 Documentation

| Guide | Purpose |
|-------|---------|
| **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** | Complete installation & configuration |
| **[API_GUIDE.md](docs/API_GUIDE.md)** | REST API documentation |
| **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** | Architecture, testing, contributing |
| **[CACHING_GUIDE.md](docs/CACHING_GUIDE.md)** | LLM response caching for cost optimization |
| **[AI_ENGINEERING_GUIDE.md](docs/AI_ENGINEERING_GUIDE.md)** | AI engineering best practices & patterns |
| **[.env.example](.env.example)** | Configuration reference |

---

## 💰 Cost Optimization & Observability

### LLM Response Caching
Reduce AI costs by 30-90% with transparent response caching:

```bash
# Enable caching (enabled by default)
FINCLI_CACHE_ENABLED=true
FINCLI_CACHE_TTL_SECONDS=3600  # 1 hour

# Typical savings:
# - Development: 70-90% cost reduction
# - Production: 30-50% cost reduction
# - Batch processing: 40-60% cost reduction
```

**Features:**
- Automatic cache key generation (prompt + model + params)
- TTL-based expiration with LRU eviction
- Optional disk persistence across restarts
- Hit/miss metrics and cost tracking

See **[CACHING_GUIDE.md](docs/CACHING_GUIDE.md)** for complete documentation.

### Metrics & Cost Tracking

Track every LLM call with built-in observability:

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()
report = tracker.get_summary_report()

print(f"Total cost: ${report['total_cost_usd']:.4f}")
print(f"Cache hit rate: {report['cache_stats']['hit_rate']:.1%}")
print(f"Success rate: {report['success_rate']:.1%}")
print(f"P95 latency: {report['latency_stats']['p95']:.0f}ms")
```

**Metrics tracked:**
- Token usage (input/output) per provider/model
- Cost calculation with provider-specific pricing
- Success/failure rates
- Latency statistics (p50, p95, p99, mean, max)
- Cache performance (hit rate, savings)

### Prompt Management

Version-controlled prompts with YAML configuration:

```bash
fincli/prompts/
├── extraction/
│   ├── transaction_v1.yaml  # Original prompt
│   └── transaction_v2.yaml  # Improved version
├── analysis/
│   └── spending_summary.yaml
└── chat/
    └── financial_advisor.yaml
```

**Benefits:**
- A/B testing different prompt versions
- Centralized prompt management
- Easy prompt updates without code changes
- Track which prompts perform best

---

## 💻 Usage Examples

### CLI Commands

```bash
# Initialize database and test connections
python cli.py init

# Fetch and process emails
python cli.py fetch --max 50

# View spending summary
python cli.py summarize

# List recent transactions
python cli.py list-transactions --limit 20

# Interactive chat
python cli.py chat
> "How much did I spend on food this month?"
> "What was my biggest expense?"
```

### REST API

```bash
# Start API server
python run_api.py

# Access interactive documentation
open http://localhost:8000/docs
```

**API Endpoints:**
- `POST /fetch` - Fetch and process emails
- `GET /api/v1/transactions` - List transactions
- `GET /api/v1/analytics/summary` - Financial summary
- `POST /chat` - Natural language Q&A

See **[API_GUIDE.md](docs/API_GUIDE.md)** for complete API documentation.

---

## 🎯 Use Cases

### Example 1: Zero Cost Setup
```bash
# Install Ollama (free, local LLM)
brew install ollama
ollama pull llama3

# Configure FinCLI
FINCLI_LLM_PROVIDER=ollama
FINCLI_OLLAMA_MODEL_NAME=llama3
```

### Example 2: Best Quality
```bash
# Use Anthropic Claude for extraction
FINCLI_LLM_PROVIDER=anthropic
FINCLI_ANTHROPIC_API_KEY=your-key
```

### Example 3: Hybrid (Cost Optimized)
```bash
# Free Ollama for most tasks, paid Claude only for extraction
FINCLI_LLM_PROVIDER=ollama
FINCLI_LLM_EXTRACTION_PROVIDER=anthropic
FINCLI_ANTHROPIC_API_KEY=your-key
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────┐
│  CLI / REST API                  │  User Interfaces
├──────────────────────────────────┤
│  Transaction Extraction          │  Business Logic
│  Chat & Analysis                 │
├──────────────────────────────────┤
│  Observability & Metrics         │  Monitoring Layer
│  Response Caching (LRU + TTL)    │
├──────────────────────────────────┤
│  Prompt Manager (YAML)           │  Prompt Layer
├──────────────────────────────────┤
│  Database (SQLite/PostgreSQL)    │  Data Layer
├──────────────────────────────────┤
│  LLM Clients (4 providers)       │  AI Layer
│  Gmail Client                    │  External APIs
└──────────────────────────────────┘
```

**Technology Stack:**
- **CLI:** Typer + Rich (beautiful terminal UI)
- **API:** FastAPI (auto-generated docs, async)
- **Database:** SQLAlchemy 2.0 + SQLite/PostgreSQL
- **AI:** Multi-provider (Ollama, Bedrock, OpenAI, Anthropic)
- **Config:** Pydantic v2 (type-safe, validated)
- **Logging:** Structlog (structured, JSON)
- **Testing:** Pytest (106/106 tests passing)

---

## 🔒 Security & Privacy

- ✅ **Read-only Gmail access** (`gmail.readonly` scope)
- ✅ **Local data storage** (no cloud sync)
- ✅ **Credentials never committed** (`.gitignore`)
- ✅ **Environment-based secrets** (`.env` file)
- ✅ **No data sharing** with AI providers (local Ollama option available)

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=fincli --cov-report=html

# View coverage report
open htmlcov/index.html
```

**Current Status:** ✅ 106/106 tests passing (100%)

See **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md#testing)** for testing documentation.

---

## 🤝 Contributing

Contributions welcome! Please:

1. Read **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** for architecture & setup
2. Fork the repository
3. Create a feature branch
4. Add tests for new features
5. Ensure all tests pass (`pytest`)
6. Run code quality checks (`black`, `ruff`, `mypy`)
7. Submit a pull request

See **[DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md#contributing)** for detailed guidelines.

---

## 📊 Project Status

- **Version:** 1.0.0
- **Status:** ✅ Production Ready
- **Tests:** ✅ 106/106 passing
- **Coverage:** 60%
- **Python:** 3.8+
- **License:** MIT

---

## 🆕 Recent Updates (v1.0.0)

**Core Features:**
- ✅ Multi-provider LLM support (4 providers)
- ✅ REST API with FastAPI
- ✅ Improved error handling & exception flow
- ✅ Email date parsing fix
- ✅ Pydantic v2 compatibility
- ✅ Updated test suite (106/106 tests passing)
- ✅ Comprehensive documentation

**Cost Optimization & Engineering:**
- ✅ LLM response caching system (30-90% cost reduction)
- ✅ Observability & metrics tracking (costs, tokens, latency)
- ✅ Prompt versioning with YAML management
- ✅ Cache statistics and performance monitoring
- ✅ Example scripts (`cache_demo.py`, `observability_demo.py`)

---

## 📖 Documentation Quick Links

- **Getting Started:** [SETUP_GUIDE.md](docs/SETUP_GUIDE.md)
- **API Reference:** [API_GUIDE.md](docs/API_GUIDE.md)
- **Development:** [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)
- **Cost Optimization:** [CACHING_GUIDE.md](docs/CACHING_GUIDE.md)
- **AI Engineering:** [AI_ENGINEERING_GUIDE.md](docs/AI_ENGINEERING_GUIDE.md)
- **Configuration:** [.env.example](.env.example)
- **Examples:** [examples/](examples/)

