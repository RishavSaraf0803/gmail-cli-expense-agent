# FinCLI Examples

This directory contains example scripts demonstrating FinCLI's features.

## Available Examples

### observability_demo.py

Demonstrates the new AI engineering features:
- LLM metrics tracking
- Prompt management
- Cost analysis
- A/B testing

**Run it:**
```bash
python examples/observability_demo.py
```

**What it shows:**
- Current metrics summary
- Cost breakdown by provider and use case
- Available prompts
- Prompt version comparison
- Latency statistics

### cache_demo.py

Demonstrates LLM response caching for cost optimization:
- Cache hit/miss behavior
- Cost savings calculation (70%+ in development)
- Cache statistics and monitoring
- Cache key sensitivity
- Integration with observability

**Run it:**
```bash
python examples/cache_demo.py
```

**What it shows:**
- Basic cache functionality
- Real cost savings examples
- Cache performance metrics
- Best practices for cache configuration
- Observability integration

## Requirements

Install dependencies first:
```bash
pip install -r requirements.txt
```

## Future Examples

Coming soon:
- `extraction_pipeline.py` - Complete email-to-database pipeline
- `cost_optimization.py` - Cost optimization strategies
- `ab_testing.py` - Full A/B testing workflow
- `custom_prompts.py` - Creating custom prompts
- `evaluation.py` - Evaluating extraction quality
