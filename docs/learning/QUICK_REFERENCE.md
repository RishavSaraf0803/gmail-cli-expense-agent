# AI Engineering Quick Reference

A quick reference guide for common patterns, code snippets, and best practices in FinCLI.

---

## 🎯 Common Code Patterns

### 1. Using LLM Router

```python
from fincli.clients.llm_router import get_llm_router, LLMUseCase

# Get router instance
router = get_llm_router()

# Extract structured data
transaction_data = router.extract_json(
    prompt=email_text,
    use_case=LLMUseCase.EXTRACTION,
    system_prompt="You are a financial transaction extractor..."
)

# Generate conversational response
answer = router.generate_text(
    prompt="How much did I spend on food?",
    use_case=LLMUseCase.CHAT,
    temperature=0.7
)

# Get routing configuration
config = router.get_routing_config()
# {'extraction': 'anthropic', 'chat': 'openai', ...}
```

---

### 2. Working with Prompts

```python
from fincli.prompts import get_prompt_manager

pm = get_prompt_manager()

# Load specific version
prompt = pm.load_prompt('extraction', 'transaction', version='v2')

# Render with variables
user_prompt = prompt.render_user_prompt(
    email_content=email_body
)

# Get parameters
temp = prompt.get_parameter('temperature', default=0.7)
max_tokens = prompt.get_parameter('max_tokens', default=1000)

# Access metadata
metrics = prompt.metadata.get('performance_metrics', {})
```

---

### 3. Cache Operations

```python
from fincli.cache.llm_cache import get_llm_cache

cache = get_llm_cache()

# Manual cache operations
cache_key = cache.generate_key(prompt, model, params)

# Check cache
if cached := cache.get(cache_key):
    return cached

# Store in cache
cache.set(cache_key, response, ttl=3600)

# Get cache statistics
stats = cache.get_cache_info()
print(f"Hit rate: {stats['hit_rate']:.1%}")
print(f"Size: {stats['size']} / {stats['max_size']}")

# Clear cache
cache.clear()
```

---

### 4. Observability & Metrics

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()

# Get summary report
report = tracker.get_summary_report()
print(f"Total cost: ${report['total_cost_usd']:.4f}")
print(f"Success rate: {report['success_rate']:.1%}")

# Get cost by provider
costs = tracker.get_cost_by_provider()
for provider, cost in costs.items():
    print(f"{provider}: ${cost:.4f}")

# Get latency statistics
latency = tracker.get_latency_stats()
print(f"P95: {latency['p95']:.0f}ms")
print(f"Mean: {latency['mean']:.0f}ms")

# Export metrics
tracker.export_to_json('metrics_export.json')
```

---

### 5. Transaction Extraction

```python
from fincli.extractors import get_transaction_extractor
from fincli.clients.gmail_client import GmailClient

# Get extractor
extractor = get_transaction_extractor()

# Or create with specific config
from fincli.extractors import TransactionExtractor
extractor = TransactionExtractor(
    prompt_version='v2',
    use_router=True,
    enable_cache=True
)

# Extract from single email
gmail = GmailClient()
emails = gmail.fetch_messages(max_results=10)

for email in emails:
    transaction = extractor.extract_from_email(email)
    
    if transaction and transaction.is_valid():
        print(f"Amount: {transaction.amount}")
        print(f"Merchant: {transaction.merchant}")
        print(f"Date: {transaction.transaction_date}")

# Batch extraction
results = extractor.extract_batch(emails)
for email, transaction in results:
    if transaction:
        print(f"Extracted from {email.subject}")
```

---

### 6. Database Operations

```python
from fincli.storage.database import DatabaseManager

db = DatabaseManager()

# Add transaction
db.add_transaction(
    email_id='msg_123',
    amount=500.0,
    transaction_type='debit',
    merchant='Starbucks',
    transaction_date=datetime.now(),
    currency='INR'
)

# Query transactions
transactions = db.get_transactions(
    start_date=datetime(2024, 11, 1),
    end_date=datetime(2024, 11, 30),
    transaction_type='debit'
)

# Get summary
summary = db.get_spending_summary(
    start_date=datetime(2024, 11, 1),
    end_date=datetime(2024, 11, 30)
)
print(f"Total: {summary['total']}")
print(f"Count: {summary['count']}")

# Top merchants
top_merchants = db.get_top_merchants(limit=10)
for merchant, total in top_merchants:
    print(f"{merchant}: ₹{total:.2f}")
```

---

### 7. Configuration Management

```python
from fincli.config import get_settings, reload_settings

# Get settings
settings = get_settings()

# Access configuration
print(f"LLM Provider: {settings.llm_provider}")
print(f"Cache Enabled: {settings.cache_enabled}")
print(f"Log Level: {settings.log_level}")

# Reload settings (after .env changes)
reload_settings()

# Environment-specific settings
if settings.debug:
    print("Debug mode enabled")
```

---

### 8. Logging

```python
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

# Structured logging
logger.info(
    "transaction_extracted",
    amount=500.0,
    merchant="Starbucks",
    email_id="msg_123"
)

logger.error(
    "extraction_failed",
    error=str(e),
    email_id="msg_123",
    exc_info=True
)

logger.debug(
    "cache_hit",
    cache_key=key,
    use_case="extraction"
)
```

---

## 🎨 Design Pattern Implementations

### Factory Pattern

```python
# fincli/clients/llm_factory.py
def create_llm_client(provider: str) -> BaseLLMClient:
    """Factory for creating LLM clients."""
    if provider == "ollama":
        return get_ollama_client()
    elif provider == "anthropic":
        return get_anthropic_client()
    elif provider == "openai":
        return get_openai_client()
    elif provider == "bedrock":
        return get_bedrock_client()
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

### Strategy Pattern

```python
# Different strategies for LLM calls
class BaseLLMClient(ABC):
    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        pass

# Concrete strategies
class OllamaClient(BaseLLMClient):
    def generate_text(self, prompt: str) -> str:
        # Ollama-specific implementation
        pass

class AnthropicClient(BaseLLMClient):
    def generate_text(self, prompt: str) -> str:
        # Anthropic-specific implementation
        pass
```

### Singleton Pattern

```python
# Global singleton instances
_llm_router: Optional[LLMRouter] = None

def get_llm_router() -> LLMRouter:
    """Get or create LLM router singleton."""
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter()
    return _llm_router
```

### Decorator Pattern

```python
# Cache decorator
def with_cache(ttl: int = 3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_llm_cache()
            key = cache.generate_key(args, kwargs)
            
            if cached := cache.get(key):
                return cached
            
            result = func(*args, **kwargs)
            cache.set(key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

@with_cache(ttl=3600)
def expensive_llm_call(prompt: str) -> str:
    return llm_client.generate_text(prompt)
```

---

## ⚡ Performance Optimization Tips

### 1. Batch Processing

```python
# Bad: Process one at a time
for email in emails:
    transaction = extractor.extract_from_email(email)
    db.add_transaction(transaction)

# Good: Batch processing
transactions = extractor.extract_batch(emails)
db.add_transactions_batch(transactions)
```

### 2. Use Caching Effectively

```python
# Enable caching for repeated queries
extractor = TransactionExtractor(enable_cache=True)

# Set appropriate TTL
cache.set(key, value, ttl=3600)  # 1 hour for stable data
cache.set(key, value, ttl=300)   # 5 min for dynamic data
```

### 3. Optimize Database Queries

```python
# Bad: N+1 queries
for transaction in transactions:
    merchant = db.get_merchant(transaction.merchant_id)

# Good: Join or batch fetch
transactions_with_merchants = db.get_transactions_with_merchants()
```

### 4. Use Appropriate LLM Provider

```python
# Use cheap/free models for non-critical tasks
router.generate_text(
    prompt="Summarize spending",
    use_case=LLMUseCase.SUMMARY  # Routes to Ollama (free)
)

# Use expensive models only for critical tasks
router.extract_json(
    prompt=email_text,
    use_case=LLMUseCase.EXTRACTION  # Routes to Claude (accurate)
)
```

---

## 🐛 Common Pitfalls & Solutions

### 1. Cache Key Collisions

```python
# Bad: Simple hash might collide
cache_key = hash(prompt)

# Good: Include all relevant parameters
cache_key = cache.generate_key(
    prompt=prompt,
    model=model,
    temperature=temperature,
    max_tokens=max_tokens
)
```

### 2. Not Handling LLM Failures

```python
# Bad: No error handling
result = llm_client.generate_text(prompt)

# Good: Handle errors gracefully
try:
    result = llm_client.generate_text(prompt)
except Exception as e:
    logger.error("llm_call_failed", error=str(e))
    # Fallback logic
    result = fallback_extraction(email)
```

### 3. Ignoring Token Limits

```python
# Bad: Might exceed token limit
result = llm_client.generate_text(very_long_prompt)

# Good: Check and truncate
MAX_TOKENS = 4000
if len(prompt) > MAX_TOKENS * 4:  # Rough estimate
    prompt = prompt[:MAX_TOKENS * 4]
    logger.warning("prompt_truncated", original_length=len(prompt))
```

### 4. Not Validating LLM Output

```python
# Bad: Trust LLM output blindly
transaction = json.loads(llm_response)

# Good: Validate and clean
try:
    data = json.loads(llm_response)
    cleaned_data = validate_and_clean(data)
    transaction = ExtractedTransaction(**cleaned_data)
except (json.JSONDecodeError, ValidationError) as e:
    logger.error("invalid_llm_output", error=str(e))
    return None
```

---

## 🧪 Testing Patterns

### 1. Mocking LLM Calls

```python
import pytest
from unittest.mock import Mock, patch

def test_transaction_extraction():
    # Mock LLM response
    mock_response = {
        "amount": 500.0,
        "merchant": "Starbucks",
        "transaction_type": "debit",
        "transaction_date": "2024-11-15"
    }
    
    with patch('fincli.clients.llm_router.LLMRouter.extract_json') as mock:
        mock.return_value = mock_response
        
        extractor = TransactionExtractor()
        result = extractor.extract_from_email(test_email)
        
        assert result.amount == 500.0
        assert result.merchant == "Starbucks"
```

### 2. Testing with Fixtures

```python
@pytest.fixture
def sample_email():
    return EmailMessage(
        message_id='test_123',
        subject='Transaction Alert',
        body='Your card was debited ₹500 at Starbucks',
        sender='bank@example.com',
        date=datetime.now()
    )

def test_extraction(sample_email):
    extractor = TransactionExtractor()
    result = extractor.extract_from_email(sample_email)
    assert result is not None
```

### 3. Integration Tests

```python
def test_end_to_end_extraction():
    """Test complete extraction pipeline."""
    # Setup
    db = DatabaseManager(db_path=':memory:')
    extractor = TransactionExtractor()
    
    # Execute
    transaction = extractor.extract_from_email(test_email)
    db.add_transaction(**transaction.to_dict())
    
    # Verify
    saved = db.get_transaction_by_email_id(test_email.message_id)
    assert saved.amount == transaction.amount
```

---

## 📊 Monitoring & Debugging

### 1. Check LLM Health

```python
from fincli.clients.llm_router import get_llm_router

router = get_llm_router()

# Check all providers
health = router.health_check()
for provider, status in health.items():
    print(f"{provider}: {'✅' if status else '❌'}")

# Check specific use case
health = router.health_check(use_case=LLMUseCase.EXTRACTION)
```

### 2. Debug Cache Issues

```python
from fincli.cache.llm_cache import get_llm_cache

cache = get_llm_cache()

# Get detailed stats
info = cache.get_cache_info()
print(f"Size: {info['size']} / {info['max_size']}")
print(f"Hits: {info['hits']}, Misses: {info['misses']}")
print(f"Hit Rate: {info['hit_rate']:.1%}")

# Check if specific key exists
key = cache.generate_key(prompt, model, params)
if cache.get(key):
    print("Found in cache")
else:
    print("Not cached")
```

### 3. Analyze Metrics

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()

# Find expensive operations
report = tracker.get_summary_report()
if report['total_cost_usd'] > 10.0:
    print("⚠️ High costs detected!")
    
    # Break down by use case
    costs = tracker.get_cost_by_use_case()
    for use_case, cost in sorted(costs.items(), key=lambda x: x[1], reverse=True):
        print(f"{use_case}: ${cost:.4f}")
```

---

## 🔧 Environment Configuration

### Development Setup

```bash
# .env.development
FINCLI_DEBUG=true
FINCLI_LOG_LEVEL=DEBUG
FINCLI_LLM_PROVIDER=ollama
FINCLI_CACHE_ENABLED=true
FINCLI_CACHE_TTL_SECONDS=3600
FINCLI_DATABASE_URL=sqlite:///fincli_dev.db
```

### Production Setup

```bash
# .env.production
FINCLI_DEBUG=false
FINCLI_LOG_LEVEL=INFO
FINCLI_LLM_PROVIDER=anthropic
FINCLI_LLM_CHAT_PROVIDER=openai
FINCLI_CACHE_ENABLED=true
FINCLI_CACHE_TTL_SECONDS=7200
FINCLI_DATABASE_URL=postgresql://user:pass@host/db
FINCLI_ANTHROPIC_API_KEY=sk-ant-...
FINCLI_OPENAI_API_KEY=sk-...
```

---

## 📝 Prompt Engineering Tips

### 1. Clear Instructions

```yaml
# Bad
system_prompt: "Extract data from email"

# Good
system_prompt: |
  You are an expert financial transaction extractor.
  Extract ONLY the following fields from transaction emails:
  - amount (float)
  - merchant (string)
  - transaction_type (debit or credit)
  - transaction_date (ISO format)
  
  Return valid JSON. If any field is missing, use null.
```

### 2. Few-Shot Examples

```yaml
user_template: |
  Extract transaction from this email:
  
  ---
  $email_content
  ---
  
  Example output:
  {
    "amount": 500.0,
    "merchant": "Starbucks",
    "transaction_type": "debit",
    "transaction_date": "2024-11-15"
  }
```

### 3. Output Constraints

```yaml
system_prompt: |
  CRITICAL: Return ONLY valid JSON. No explanations, no markdown.
  
  Required format:
  {
    "amount": <number>,
    "merchant": "<string>",
    "transaction_type": "debit" | "credit",
    "transaction_date": "<YYYY-MM-DD>"
  }
```

---

## 🎯 Best Practices Checklist

### Code Quality
- [ ] Use type hints for all functions
- [ ] Write docstrings for public APIs
- [ ] Handle errors gracefully
- [ ] Log important events
- [ ] Write tests for new features

### AI Engineering
- [ ] Cache LLM responses
- [ ] Track metrics and costs
- [ ] Version your prompts
- [ ] Validate LLM outputs
- [ ] Use appropriate models for tasks

### Performance
- [ ] Batch operations when possible
- [ ] Use database indexes
- [ ] Optimize prompt length
- [ ] Monitor latency
- [ ] Set appropriate timeouts

### Security
- [ ] Never commit API keys
- [ ] Use environment variables
- [ ] Validate user inputs
- [ ] Sanitize LLM outputs
- [ ] Implement rate limiting

---

## 📚 Glossary

| Term | Definition |
|------|------------|
| **LLM** | Large Language Model (e.g., GPT-4, Claude) |
| **RAG** | Retrieval Augmented Generation - combining retrieval with generation |
| **Embedding** | Vector representation of text for semantic search |
| **Token** | Unit of text for LLM processing (~4 characters) |
| **Temperature** | Randomness in LLM output (0=deterministic, 1=creative) |
| **Few-Shot** | Providing examples in the prompt |
| **Zero-Shot** | No examples, just instructions |
| **Prompt Engineering** | Crafting effective prompts for LLMs |
| **Use Case** | Specific task type (extraction, chat, etc.) |
| **TTL** | Time To Live - how long cache entries are valid |
| **LRU** | Least Recently Used - cache eviction strategy |
| **Observability** | Monitoring, logging, and metrics |
| **Latency** | Time taken to complete a request |
| **P95** | 95th percentile - 95% of requests are faster |

---

## 🚀 Quick Commands

```bash
# Development
python cli.py init                    # Initialize database
python cli.py fetch --max 20          # Fetch emails
python cli.py list-transactions       # List transactions
python cli.py summarize               # Show summary
python cli.py chat                    # Interactive chat
python cli.py metrics                 # Show metrics

# Testing
pytest                                # Run all tests
pytest -v                             # Verbose output
pytest --cov=fincli                   # With coverage
pytest tests/test_extractor.py        # Specific test

# API
python run_api.py                     # Start API server
open http://localhost:8000/docs       # API documentation

# Monitoring
python cli.py cache-stats             # Cache statistics
python cli.py metrics --export report.json  # Export metrics
```

---

## 🔗 Useful Links

- **Project Docs:** [`docs/`](file:///Users/rishavsaraf/Desktop/touch/Development/AI_Agents/gmail-cli-expense-agent/docs/)
- **Examples:** [`examples/`](file:///Users/rishavsaraf/Desktop/touch/Development/AI_Agents/gmail-cli-expense-agent/examples/)
- **Tests:** [`tests/`](file:///Users/rishavsaraf/Desktop/touch/Development/AI_Agents/gmail-cli-expense-agent/tests/)
- **Main Code:** [`fincli/`](file:///Users/rishavsaraf/Desktop/touch/Development/AI_Agents/gmail-cli-expense-agent/fincli/)

---

**Remember:** This is a living document. Update it as you learn and discover new patterns!
