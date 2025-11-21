# LLM Response Caching Guide

Complete guide to FinCLI's LLM response caching system for cost optimization.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [How It Works](#how-it-works)
5. [Cost Savings](#cost-savings)
6. [Cache Statistics](#cache-statistics)
7. [Advanced Usage](#advanced-usage)
8. [Best Practices](#best-practices)

---

## Overview

### What is Response Caching?

Response caching stores LLM outputs for identical requests, avoiding redundant API calls and reducing costs dramatically.

### Key Features

- **Transparent caching** - No code changes required
- **Smart cache keys** - Hash of prompt + model + parameters
- **TTL support** - Automatic expiration (default: 1 hour)
- **LRU eviction** - Removes least recently used entries
- **Disk persistence** - Optional persistent cache across restarts
- **Cost tracking** - Calculate savings from cache hits
- **Hit/miss metrics** - Track cache performance

### When Does Caching Help?

**High Impact Scenarios:**
- Repeated queries (same question multiple times)
- Similar transactions (common merchants, amounts)
- Batch processing with duplicates
- Development/testing (same test emails)
- Demo environments

**Typical Savings:**
- **Development**: 70-90% cost reduction
- **Production**: 30-50% cost reduction
- **Batch processing**: 40-60% cost reduction

---

## Quick Start

### Enable Caching (Default)

Caching is **enabled by default**. Just use FinCLI normally:

```python
from fincli.extractors import TransactionExtractor

# Cache automatically enabled
extractor = TransactionExtractor()
transaction = extractor.extract_from_email(email)
```

### View Cache Stats

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()
report = tracker.get_summary_report()

# Check cache performance
cache_stats = report['cache_stats']
print(f"Hit rate: {cache_stats['hit_rate']:.1%}")
print(f"Tokens saved: {cache_stats['tokens_saved']:,}")
print(f"Cost saved: ${cache_stats['cost_saved_usd']:.4f}")
```

### Disable Caching

```python
# Disable for specific extractor
extractor = TransactionExtractor(enable_cache=False)

# Or disable globally in .env
FINCLI_CACHE_ENABLED=false
```

---

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Cache Settings
FINCLI_CACHE_ENABLED=true                  # Enable/disable caching
FINCLI_CACHE_TTL_SECONDS=3600             # Cache TTL (1 hour default)
FINCLI_CACHE_MAX_ENTRIES=1000             # Max cache entries
FINCLI_CACHE_ENABLE_DISK=false            # Enable persistent disk cache
FINCLI_CACHE_DIR=.fincli_cache            # Disk cache directory
```

### Configuration Options

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| `cache_enabled` | `true` | bool | Enable/disable caching |
| `cache_ttl_seconds` | `3600` | 60-86400 | Cache expiration time |
| `cache_max_entries` | `1000` | 10-10000 | Max entries (LRU) |
| `cache_enable_disk` | `false` | bool | Persistent disk cache |
| `cache_dir` | `.fincli_cache` | path | Cache directory |

### TTL Guidelines

- **Development**: 24 hours (`86400` seconds)
- **Production**: 1 hour (`3600` seconds)
- **Testing**: 5 minutes (`300` seconds)
- **Real-time data**: 1 minute (`60` seconds)

---

## How It Works

### Cache Key Generation

Cache keys are SHA256 hashes of:
- User prompt
- System prompt
- Model name
- Provider name
- Temperature
- Max tokens
- Use case
- Additional parameters

**Example:**
```python
# These will generate DIFFERENT cache keys:
extract(prompt="Spent ₹500", temperature=0.0)  # Key: abc123...
extract(prompt="Spent ₹500", temperature=0.7)  # Key: def456...

# These will generate the SAME cache key:
extract(prompt="Spent ₹500", temperature=0.0)  # Key: abc123...
extract(prompt="Spent ₹500", temperature=0.0)  # Key: abc123... (cache hit!)
```

### Cache Lifecycle

```
1. Request arrives
    ↓
2. Generate cache key (SHA256 hash)
    ↓
3. Check in-memory cache
    ↓
4. Is cached? → Yes → Check expiration
    ├─ Expired? → Remove & miss
    └─ Valid? → Return cached response (HIT)
    ↓
5. Not cached → Call LLM API
    ↓
6. Store response in cache
    ↓
7. Check size limit → Evict oldest if needed (LRU)
    ↓
8. Optionally save to disk
```

### LRU Eviction

When cache reaches `max_entries`:
1. Oldest entry (least recently used) is removed
2. New entry is added
3. Eviction counter increments

**Access updates LRU order:**
- Every cache hit moves entry to "most recent"
- Ensures frequently used entries stay cached

### Disk Persistence

When `cache_enable_disk=true`:
- **On write**: Entry saved to `.fincli_cache/{hash}.pkl`
- **On startup**: Cache loads from disk
- **Expired entries**: Deleted on load
- **Format**: Python pickle (fast, binary)

---

## Cost Savings

### Calculate Savings

```python
from fincli.cache import get_cache_manager

cache_manager = get_cache_manager()

# Calculate savings for specific provider/model
cache_manager.calculate_cost_savings(
    provider="anthropic",
    model="claude-3-5-sonnet",
    input_cost_per_1k=0.003,   # $0.003 per 1K input tokens
    output_cost_per_1k=0.015   # $0.015 per 1K output tokens
)

stats = cache_manager.get_stats()
print(f"Saved: ${stats.cost_saved_usd:.2f}")
```

### Example Savings

**Scenario: Batch processing 1000 emails with 20% duplicates**

Without cache:
- 1000 API calls
- ~850K tokens
- Cost: ~$4.50

With cache:
- 800 API calls (200 cache hits)
- ~680K tokens
- Cost: ~$3.60
- **Savings: $0.90 (20%)**

**Scenario: Development with test data**

Without cache:
- 100 test runs
- Same 10 test emails
- 1000 API calls
- Cost: ~$5.00

With cache:
- 100 test runs
- 10 API calls (990 cache hits)
- Cost: ~$0.05
- **Savings: $4.95 (99%)**

### Cost Tracking in Observability

```python
from fincli.observability import get_metrics_tracker

tracker = get_metrics_tracker()
report = tracker.get_summary_report()

print("=== Cost Report ===")
print(f"Total API cost: ${report['total_cost_usd']:.4f}")
print(f"Cache hit rate: {report['cache_stats']['hit_rate']:.1%}")
print(f"Cache savings: ${report['cache_stats']['cost_saved_usd']:.4f}")
print(f"Effective cost: ${report['total_cost_usd'] - report['cache_stats']['cost_saved_usd']:.4f}")
```

---

## Cache Statistics

### Available Metrics

```python
from fincli.cache import get_cache_manager

cache_manager = get_cache_manager()
stats = cache_manager.get_stats()

print(f"Total hits: {stats.total_hits}")
print(f"Total misses: {stats.total_misses}")
print(f"Hit rate: {stats.hit_rate:.1%}")
print(f"Entries: {stats.total_entries}")
print(f"Evictions: {stats.total_evictions}")
print(f"Tokens saved: {stats.tokens_saved:,}")
print(f"Cost saved: ${stats.cost_saved_usd:.4f}")
```

### Export Statistics

```python
from pathlib import Path

# Export to JSON
cache_manager.export_stats(Path("cache_report.json"))
```

**Output:**
```json
{
  "total_hits": 450,
  "total_misses": 550,
  "hit_rate": 0.45,
  "total_entries": 320,
  "total_evictions": 12,
  "tokens_saved": 125000,
  "cost_saved_usd": 0.525
}
```

### Monitor Cache Performance

```python
# Get initial stats
stats_before = cache_manager.get_stats()

# Run operations...
for email in emails:
    extractor.extract_from_email(email)

# Check improvement
stats_after = cache_manager.get_stats()

new_hits = stats_after.total_hits - stats_before.total_hits
new_total = (stats_after.total_hits + stats_after.total_misses) - \
            (stats_before.total_hits + stats_before.total_misses)

print(f"Batch hit rate: {new_hits/new_total:.1%}")
```

---

## Advanced Usage

### Direct Cache Manager Usage

```python
from fincli.cache import get_cache_manager

cache_manager = get_cache_manager()

# Check for cached response
cached = cache_manager.get(
    prompt="Your card ending in 1234 was debited...",
    model="claude-3-5-sonnet",
    provider="anthropic",
    temperature=0.0,
    max_tokens=500
)

if cached:
    print("Cache hit!")
    result = cached
else:
    # Call LLM
    result = llm_client.generate_text(...)

    # Store in cache
    cache_manager.set(
        prompt="Your card ending in 1234...",
        response=result,
        model="claude-3-5-sonnet",
        provider="anthropic",
        input_tokens=850,
        output_tokens=120,
        temperature=0.0,
        max_tokens=500
    )
```

### Custom Cache Configuration

```python
from fincli.cache import get_cache_manager

# Custom TTL and size
cache_manager = get_cache_manager(
    ttl_seconds=7200,      # 2 hours
    max_entries=5000,      # 5000 entries
    enable_disk_cache=True # Enable persistence
)
```

### Clear Cache

```python
# Clear all cached entries
cache_manager.clear()

# Or clear via wrapper
from fincli.cache import LLMCache

cached_client = LLMCache(llm_client)
cached_client.clear_cache()
```

### Decorator Pattern

```python
from fincli.cache import cached_llm_call

@cached_llm_call
def custom_extraction(prompt, model="claude-3-5-sonnet"):
    # Your LLM call here
    return client.generate_text(prompt, model=model)

# First call - API hit
result1 = custom_extraction("Extract transaction from email...")

# Second call - cache hit!
result2 = custom_extraction("Extract transaction from email...")
```

---

## Best Practices

### 1. Use Appropriate TTL

```python
# Real-time data - short TTL
extractor_realtime = TransactionExtractor()
# .env: FINCLI_CACHE_TTL_SECONDS=300  # 5 minutes

# Historical analysis - long TTL
extractor_batch = TransactionExtractor()
# .env: FINCLI_CACHE_TTL_SECONDS=86400  # 24 hours
```

### 2. Monitor Cache Hit Rate

**Target hit rates:**
- **Development**: >80%
- **Production**: >30%
- **Batch processing**: >40%

**If hit rate is low:**
- Increase `cache_max_entries`
- Increase `cache_ttl_seconds`
- Check for parameter variations (temperature, max_tokens)

### 3. Use Disk Cache for Long-Running Processes

```bash
# .env for long-running services
FINCLI_CACHE_ENABLE_DISK=true
FINCLI_CACHE_TTL_SECONDS=86400
```

**Benefits:**
- Cache survives restarts
- Faster warm-up time
- Better for scheduled jobs

### 4. Disable Cache for Real-Time Critical Operations

```python
# Disable for time-sensitive operations
extractor = TransactionExtractor(enable_cache=False)
```

**When to disable:**
- Real-time fraud detection
- Live market data
- User-specific personalization
- Sensitive/PII data

### 5. Test Cache Behavior

```python
def test_caching():
    """Test that caching works correctly."""
    from fincli.cache import get_cache_manager

    cache_manager = get_cache_manager()
    cache_manager.clear()  # Start fresh

    extractor = TransactionExtractor()

    # First call - cache miss
    result1 = extractor.extract_from_email(test_email)
    stats1 = cache_manager.get_stats()
    assert stats1.total_misses == 1
    assert stats1.total_hits == 0

    # Second call - cache hit
    result2 = extractor.extract_from_email(test_email)
    stats2 = cache_manager.get_stats()
    assert stats2.total_hits == 1
    assert result1.amount == result2.amount
```

### 6. Periodic Cache Analysis

```python
# Weekly cache report
from fincli.cache import get_cache_manager
from datetime import datetime

cache_manager = get_cache_manager()
stats = cache_manager.get_stats()

report_file = f"cache_report_{datetime.now().strftime('%Y%m%d')}.json"
cache_manager.export_stats(Path(report_file))

print(f"""
Weekly Cache Report:
- Hit rate: {stats.hit_rate:.1%}
- Cost saved: ${stats.cost_saved_usd:.2f}
- Tokens saved: {stats.tokens_saved:,}
- Recommendation: {'Increase TTL' if stats.hit_rate < 0.3 else 'Current settings optimal'}
""")
```

### 7. Optimize Prompt Parameters

**Cache-friendly prompts:**
- Use deterministic temperature (0.0)
- Standardize max_tokens
- Consistent system prompts
- Normalize input format

**Example:**
```python
# Bad - variable parameters reduce hit rate
extract(prompt, temperature=random.uniform(0, 1))

# Good - consistent parameters increase hit rate
extract(prompt, temperature=0.0, max_tokens=500)
```

---

## Troubleshooting

### Low Hit Rate

**Problem**: Hit rate < 20%

**Solutions:**
1. Check parameter consistency
2. Increase `cache_max_entries`
3. Normalize prompts (trim whitespace, lowercase)
4. Use longer TTL

### High Memory Usage

**Problem**: Cache consuming too much memory

**Solutions:**
1. Reduce `cache_max_entries`
2. Enable disk cache
3. Reduce `cache_ttl_seconds`
4. Clear cache periodically

### Stale Cache Entries

**Problem**: Getting outdated responses

**Solutions:**
1. Reduce `cache_ttl_seconds`
2. Clear cache manually
3. Disable cache for real-time operations

### Cache Miss for Identical Requests

**Problem**: Same request hitting API twice

**Possible causes:**
1. Different parameter values
2. Different whitespace in prompt
3. Cache was cleared
4. Entry expired (TTL)

**Debug:**
```python
from fincli.cache import get_cache_manager

cache_manager = get_cache_manager()

# Check cache key generation
key1 = cache_manager._generate_cache_key(
    prompt="test", model="claude", provider="anthropic", temperature=0.0
)
key2 = cache_manager._generate_cache_key(
    prompt="test ", model="claude", provider="anthropic", temperature=0.0
)

print(f"Keys match: {key1 == key2}")  # False - trailing space!
```

---

## Examples

### Example 1: Batch Processing with Cache

```python
from fincli.extractors import TransactionExtractor
from fincli.clients.gmail_client import GmailClient
from fincli.cache import get_cache_manager

# Initialize
gmail = GmailClient()
extractor = TransactionExtractor(enable_cache=True)
cache_manager = get_cache_manager()

# Clear cache for fresh start
cache_manager.clear()

# Fetch emails
emails = gmail.fetch_messages(max_results=100)

print(f"Processing {len(emails)} emails...")

# Process batch
for email in emails:
    transaction = extractor.extract_from_email(email)
    if transaction and transaction.is_valid():
        # Save to database
        pass

# Check cache performance
stats = cache_manager.get_stats()
print(f"\nCache Performance:")
print(f"  Hits: {stats.total_hits}")
print(f"  Misses: {stats.total_misses}")
print(f"  Hit Rate: {stats.hit_rate:.1%}")
print(f"  Cost Saved: ${stats.cost_saved_usd:.4f}")
```

### Example 2: A/B Testing with Cache

```python
# Test two prompt versions with caching
from fincli.extractors import TransactionExtractor
from fincli.cache import get_cache_manager

# Both use cache - second version reuses results
extractor_v1 = TransactionExtractor(prompt_version='v1', enable_cache=True)
extractor_v2 = TransactionExtractor(prompt_version='v2', enable_cache=True)

test_emails = [...] # Your test set

results_v1 = []
results_v2 = []

for email in test_emails:
    # Both extractors share cache (same prompts)
    r1 = extractor_v1.extract_from_email(email)
    r2 = extractor_v2.extract_from_email(email)
    results_v1.append(r1)
    results_v2.append(r2)

# Cache reduces cost of A/B testing!
cache_manager = get_cache_manager()
print(f"A/B test cost savings: ${cache_manager.get_stats().cost_saved_usd:.4f}")
```

### Example 3: Development with Persistent Cache

```bash
# .env configuration for development
FINCLI_CACHE_ENABLED=true
FINCLI_CACHE_TTL_SECONDS=86400      # 24 hours
FINCLI_CACHE_ENABLE_DISK=true       # Persist across restarts
FINCLI_CACHE_MAX_ENTRIES=5000       # Large cache for dev
```

```python
# Use normally - cache persists across runs
from fincli.extractors import TransactionExtractor

extractor = TransactionExtractor()

# First run: Populates cache
# Subsequent runs: Use cached responses (even after restart!)
transaction = extractor.extract_from_email(email)
```

---

## Resources

- **Main Documentation**: `docs/AI_ENGINEERING_GUIDE.md`
- **Demo Script**: `examples/cache_demo.py`
- **Configuration**: See `.env.example` for all settings
- **Module Code**: `fincli/cache/`

For questions or issues, see `docs/DEVELOPER_GUIDE.md`.
