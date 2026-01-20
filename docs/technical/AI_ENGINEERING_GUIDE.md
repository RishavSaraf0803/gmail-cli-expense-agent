# AI Engineering Features Guide

Complete guide to FinCLI's advanced AI engineering features including observability, prompt management, and best practices.

---

## Table of Contents

1. [LLM Observability](#llm-observability)
2. [Prompt Management](#prompt-management)
3. [Cost Tracking](#cost-tracking)
4. [A/B Testing Prompts](#ab-testing-prompts)
5. [Best Practices](#best-practices)

---

## LLM Observability

### Overview

FinCLI includes comprehensive LLM observability to track:
- Token usage (input/output)
- Costs per provider
- Latency metrics
- Success/failure rates
- Use-case breakdown

### Automatic Tracking

All LLM calls are automatically tracked with:
- Provider (anthropic, openai, bedrock, ollama)
- Model used
- Use case (extraction, chat, analysis, summary)
- Token counts
- Latency
- Cost calculation
- Success status

### Viewing Metrics

```bash
# View metrics summary
python cli.py metrics

# Export metrics to JSON
python cli.py metrics --export metrics_report.json

# View metrics for specific provider
python cli.py metrics --provider anthropic

# View metrics for specific use case
python cli.py metrics --use-case extraction
```

### Programmatic Access

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()

# Get summary report
report = tracker.get_summary_report()
print(f"Total cost: ${report['total_cost_usd']:.4f}")
print(f"Success rate: {report['success_rate']:.2%}")

# Get cost by provider
costs = tracker.get_cost_by_provider()
for provider, cost in costs.items():
    print(f"{provider}: ${cost:.4f}")

# Get latency stats
latency = tracker.get_latency_stats()
print(f"P95 latency: {latency['p95']:.0f}ms")

# Export for analysis
tracker.export_to_json("metrics_export.json")
```

### Metrics Storage

Metrics are stored in `fincli_metrics.jsonl` (JSON Lines format).

Each line contains:
```json
{
  "timestamp": "2024-11-19T10:30:45.123456",
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "use_case": "extraction",
  "input_tokens": 850,
  "output_tokens": 120,
  "latency_ms": 1234.56,
  "success": true,
  "error_message": null,
  "cost_usd": 0.0039
}
```

### Cost Calculation

Costs are automatically calculated based on provider pricing:

**Anthropic:**
- Claude 3.5 Sonnet: $0.003/1K input, $0.015/1K output
- Claude 3 Sonnet: $0.003/1K input, $0.015/1K output

**OpenAI:**
- GPT-4: $0.03/1K input, $0.06/1K output
- GPT-4 Turbo: $0.01/1K input, $0.03/1K output
- GPT-3.5 Turbo: $0.0005/1K input, $0.0015/1K output

**AWS Bedrock:**
- Claude 3 Sonnet: $0.003/1K input, $0.015/1K output
- Claude 3 Haiku: $0.00025/1K input, $0.00125/1K output

**Ollama:**
- All models: $0 (free local models)

---

## Prompt Management

### Overview

Prompts are versioned YAML files separate from code, enabling:
- Version control for prompts
- A/B testing
- Rapid iteration
- Performance tracking
- Rollback capabilities

### Directory Structure

```
fincli/prompts/
├── extraction/
│   ├── transaction_v1.yaml
│   ├── transaction_v2.yaml
├── chat/
│   └── financial_advisor.yaml
└── analysis/
    └── spending_summary.yaml
```

### Prompt File Format

```yaml
name: transaction_extraction
version: v2
description: Enhanced extraction with improved edge case handling

system_prompt: |
  You are an expert financial transaction extractor...

user_template: |
  Extract transaction details from this email:

  ---
  $email_content
  ---

parameters:
  temperature: 0.0
  max_tokens: 600

metadata:
  created_date: "2024-11-19"
  performance_metrics:
    target_accuracy: 0.97
    target_f1_score: 0.94
  ab_test_status: "ready"
```

### Using Prompts

#### Load and Use Prompt

```python
from fincli.prompts import get_prompt_manager

pm = get_prompt_manager()

# Load specific version
prompt = pm.load_prompt('extraction', 'transaction', version='v2')

# Render prompt with variables
user_prompt = prompt.render_user_prompt(
    email_content="Your card ending in 1234 was debited ₹500..."
)

# Get parameters
temperature = prompt.get_parameter('temperature', 0.7)
max_tokens = prompt.get_parameter('max_tokens', 1000)

# Access metadata
metrics = prompt.metadata.get('performance_metrics', {})
print(f"Target accuracy: {metrics.get('target_accuracy')}")
```

#### Use in TransactionExtractor

```python
from fincli.extractors import TransactionExtractor

# Use latest version
extractor = TransactionExtractor()

# Use specific version
extractor_v1 = TransactionExtractor(prompt_version='v1')

# Disable prompts (use legacy hardcoded)
extractor_legacy = TransactionExtractor(use_prompts=False)
```

### Creating New Prompts

1. **Create YAML file** in appropriate category directory
2. **Follow naming convention**: `{name}_{version}.yaml` or `{name}.yaml`
3. **Include all required fields**:
   - `name`
   - `version`
   - `system_prompt`
   - `user_template`
   - `parameters`
   - `metadata`

Example:
```yaml
name: receipt_extraction
version: v1
description: Extract itemized data from receipt images

system_prompt: |
  You are an expert at analyzing receipts...

user_template: |
  Extract items from this receipt:
  $receipt_text

parameters:
  temperature: 0.0
  max_tokens: 1000

metadata:
  created_date: "2024-11-19"
  author: "Your Name"
```

### Listing Available Prompts

```python
pm = get_prompt_manager()

# List all prompts
all_prompts = pm.list_prompts()
# {'extraction': ['transaction'], 'chat': ['financial_advisor'], ...}

# List prompts in category
extraction_prompts = pm.list_prompts(category='extraction')
# {'extraction': ['transaction']}
```

---

## Cost Tracking

### Real-Time Cost Monitoring

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()

# Get total cost
total = tracker.get_total_cost()
print(f"Total spend: ${total:.4f}")

# Cost by provider
by_provider = tracker.get_cost_by_provider()
# {'anthropic': 0.0234, 'openai': 0.0156, 'ollama': 0.0}

# Cost by use case
by_use_case = tracker.get_cost_by_use_case()
# {'extraction': 0.0290, 'chat': 0.0100}

# Filter by time period
from datetime import datetime, timedelta

last_30_days = tracker.get_total_cost(
    start_date=datetime.now() - timedelta(days=30)
)
```

### Cost Optimization Tips

1. **Use Ollama for development**: Free local models
2. **Route by use case**: Free Ollama for chat, paid Claude for extraction
3. **Monitor token usage**: Identify expensive operations
4. **Optimize prompts**: Shorter prompts = lower cost
5. **Cache results**: Avoid reprocessing same emails

Example hybrid setup:
```bash
# .env configuration
FINCLI_LLM_PROVIDER=ollama  # Default to free
FINCLI_LLM_EXTRACTION_PROVIDER=anthropic  # Pay only for critical task
FINCLI_ANTHROPIC_API_KEY=sk-ant-...
```

---

## A/B Testing Prompts

### Comparing Prompt Versions

```python
from fincli.extractors import TransactionExtractor
from fincli.clients.gmail_client import GmailClient

# Create extractors with different prompt versions
extractor_v1 = TransactionExtractor(prompt_version='v1')
extractor_v2 = TransactionExtractor(prompt_version='v2')

# Get test emails
gmail = GmailClient()
test_emails = gmail.fetch_messages(max_results=50)

# Run both versions
results_v1 = []
results_v2 = []

for email in test_emails:
    t1 = extractor_v1.extract_from_email(email)
    t2 = extractor_v2.extract_from_email(email)
    results_v1.append(t1)
    results_v2.append(t2)

# Compare metrics
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()

# Check which version performed better
# (analyze from metrics or manual evaluation)
```

### Evaluation Metrics

Track these metrics per prompt version:

1. **Accuracy**: % of correct extractions
2. **Precision**: % of extracted data that's correct
3. **Recall**: % of available data that was extracted
4. **Latency**: Response time
5. **Cost**: Token usage and cost

### Rolling Out New Versions

1. **Create new version**: `transaction_v3.yaml`
2. **Test on sample**: Run A/B test
3. **Evaluate metrics**: Compare to baseline
4. **Gradual rollout**:
   - Test: 10% traffic
   - Validate: Check metrics
   - Scale: 50%, then 100%
5. **Make default**: Remove version parameter

---

## Best Practices

### 1. Always Monitor Metrics

```python
# Check metrics regularly
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()
report = tracker.get_summary_report()

if report['success_rate'] < 0.95:
    print("⚠️  Success rate below threshold!")

if report['total_cost_usd'] > 10.0:
    print("⚠️  Monthly budget exceeded!")
```

### 2. Version Your Prompts

```yaml
# Good: Versioned with metadata
name: transaction_extraction
version: v2
metadata:
  changes_from_v1: "Added edge case handling"
  performance_metrics:
    accuracy: 0.97
```

### 3. Use Appropriate Providers

```python
# Use case routing for cost optimization
from fincli.clients.llm_router import LLMRouter, LLMUseCase

router = LLMRouter()

# Expensive but accurate for extraction
transaction = router.extract_json(
    prompt=email_text,
    use_case=LLMUseCase.EXTRACTION  # Uses Anthropic
)

# Cheaper for chat
answer = router.generate_text(
    prompt=question,
    use_case=LLMUseCase.CHAT  # Uses Ollama
)
```

### 4. Test Prompt Changes

Before deploying new prompts:

1. Create labeled test set (golden dataset)
2. Run both versions
3. Compare accuracy
4. Check latency and cost
5. Validate edge cases

### 5. Track Prompt Performance

```yaml
# Include performance metrics in metadata
metadata:
  performance_metrics:
    accuracy: 0.95
    f1_score: 0.92
    avg_latency_ms: 1200
    avg_cost_usd: 0.003
  test_set_size: 100
  last_evaluated: "2024-11-19"
```

### 6. Export and Analyze

```python
# Regular exports for analysis
tracker.export_to_json("monthly_metrics.json")

# Analyze in notebooks or dashboards
# - Cost trends over time
# - Provider performance comparison
# - Use case cost breakdown
# - Identify optimization opportunities
```

---

## Advanced Usage

### Custom Metrics Analysis

```python
from datetime import datetime, timedelta
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()

# Calculate cost per extraction
extraction_cost = tracker.get_total_cost(use_case='extraction')
extraction_tokens = tracker.get_total_tokens(use_case='extraction')
cost_per_1k = (extraction_cost / extraction_tokens['total_tokens']) * 1000

print(f"Cost per 1K tokens: ${cost_per_1k:.4f}")

# Provider reliability comparison
for provider in ['anthropic', 'openai', 'ollama']:
    success_rate = tracker.get_success_rate(provider=provider)
    latency = tracker.get_latency_stats(provider=provider)
    print(f"{provider}: {success_rate:.1%} success, {latency['p95']:.0f}ms p95")
```

### Prompt Template Variables

```yaml
user_template: |
  Context: $context

  Question: $question

  Additional info: $extra_info
```

```python
prompt.render_user_prompt(
    context="User has spent ₹50K this month",
    question="How can I save more?",
    extra_info="Budget: ₹60K/month"
)
```

---

## Integration Examples

### Complete Extraction Pipeline

```python
from fincli.clients.gmail_client import GmailClient
from fincli.extractors import TransactionExtractor
from fincli.storage.database import DatabaseManager
from fincli.observability import get_metrics_tracker

# Initialize
gmail = GmailClient()
extractor = TransactionExtractor(prompt_version='v2')
db = DatabaseManager()
tracker = get_metrics_tracker()

# Fetch emails
emails = gmail.fetch_messages(max_results=50)

# Extract and store
for email in emails:
    transaction = extractor.extract_from_email(email)
    if transaction and transaction.is_valid():
        db.add_transaction(
            email_id=email.message_id,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type,
            merchant=transaction.merchant,
            transaction_date=transaction.transaction_date,
            currency=transaction.currency
        )

# Check metrics
report = tracker.get_summary_report()
print(f"Processed {report['total_calls']} emails")
print(f"Success rate: {report['success_rate']:.1%}")
print(f"Total cost: ${report['total_cost_usd']:.4f}")
```

---

## Troubleshooting

### High Costs

```python
# Identify expensive operations
tracker = get_metrics_tracker()

# Check which use case costs most
costs = tracker.get_cost_by_use_case()
print("Most expensive:", max(costs, key=costs.get))

# Check token usage
tokens = tracker.get_total_tokens()
print(f"Total tokens: {tokens['total_tokens']:,}")

# Solution: Optimize prompts or switch providers
```

### Prompt Load Failures

```python
# Prompts fall back to legacy mode automatically
extractor = TransactionExtractor()  # Will use legacy if prompts fail

# Check logs for errors
# Look for: "prompt_load_failed_using_fallback"

# Validate YAML syntax
import yaml
with open('fincli/prompts/extraction/transaction_v1.yaml') as f:
    data = yaml.safe_load(f)  # Will raise on invalid YAML
```

### Low Success Rate

```python
# Analyze failures
tracker = get_metrics_tracker()

# Filter failed calls (need to implement in tracker)
# Look for patterns in error_message field

# Try different prompt version
extractor_v2 = TransactionExtractor(prompt_version='v2')

# Or different provider
from fincli.extractors import TransactionExtractor
from fincli.clients.anthropic_client import get_anthropic_client

extractor = TransactionExtractor(
    llm_client=get_anthropic_client()  # More accurate
)
```

---

## Resources

- **Metrics File**: `fincli_metrics.jsonl`
- **Prompts Directory**: `fincli/prompts/`
- **Documentation**: `docs/AI_ENGINEERING_GUIDE.md`
- **Examples**: `examples/observability_demo.py` (to be created)

For questions or issues, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).
