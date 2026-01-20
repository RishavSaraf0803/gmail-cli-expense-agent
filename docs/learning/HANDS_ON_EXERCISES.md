# Hands-On Exercises: AI Engineering with FinCLI

Practical exercises to deepen your understanding of AI engineering concepts through hands-on implementation.

---

## 🎯 Exercise Structure

Each exercise includes:
- **Objective:** What you'll build
- **Difficulty:** Beginner / Intermediate / Advanced
- **Time:** Estimated completion time
- **Prerequisites:** What you need to know first
- **Steps:** Detailed implementation guide
- **Testing:** How to verify your work
- **Learning Outcomes:** What you'll learn

---

## 📝 Exercise 1: Add a New LLM Provider

**Objective:** Implement support for Google's Gemini API

**Difficulty:** Intermediate  
**Time:** 2-3 hours  
**Prerequisites:** Understanding of `BaseLLMClient` and Factory pattern

### Steps

1. **Create the client file**

```bash
touch fincli/clients/gemini_client.py
```

2. **Implement the client**

```python
# fincli/clients/gemini_client.py
"""
Google Gemini LLM client implementation.
"""
import json
from typing import Optional, Dict, Any
import google.generativeai as genai

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.config import get_settings
from fincli.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GeminiClient(BaseLLMClient):
    """Google Gemini LLM client."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-pro"
    ):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google API key
            model_name: Model name (gemini-pro, gemini-pro-vision)
        """
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name
        
        if not self.api_key:
            raise ValueError("Gemini API key not provided")
        
        # Configure the API
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
        
        logger.info(
            "gemini_client_initialized",
            model=self.model_name
        )
    
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate text using Gemini."""
        try:
            # Combine system and user prompts
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Configure generation
            generation_config = {}
            if max_tokens:
                generation_config['max_output_tokens'] = max_tokens
            if temperature is not None:
                generation_config['temperature'] = temperature
            
            # Generate
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            logger.error(
                "gemini_generation_failed",
                error=str(e),
                prompt_length=len(prompt)
            )
            raise
    
    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Extract JSON using Gemini."""
        try:
            # Add JSON instruction to prompt
            json_prompt = f"{prompt}\n\nReturn only valid JSON, no other text."
            
            response_text = self.generate_text(
                json_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.0
            )
            
            # Clean and parse JSON
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            return json.loads(response_text.strip())
            
        except json.JSONDecodeError as e:
            logger.error(
                "gemini_json_parse_failed",
                error=str(e),
                response=response_text[:200]
            )
            raise
    
    def health_check(self) -> bool:
        """Check if Gemini is accessible."""
        try:
            response = self.generate_text(
                "Say 'OK' if you can read this.",
                max_tokens=10
            )
            return "OK" in response or "ok" in response.lower()
        except Exception as e:
            logger.error("gemini_health_check_failed", error=str(e))
            return False


def get_gemini_client() -> GeminiClient:
    """Get Gemini client instance."""
    return GeminiClient()
```

3. **Update configuration**

Add to `fincli/config.py`:

```python
# In Settings class
gemini_api_key: Optional[str] = Field(
    default=None,
    description="Google Gemini API key"
)
gemini_model_name: str = Field(
    default="gemini-pro",
    description="Gemini model name"
)
```

4. **Update factory**

Add to `fincli/clients/llm_factory.py`:

```python
from fincli.clients.gemini_client import get_gemini_client

# In create_llm_client function
elif provider == "gemini":
    return get_gemini_client()
```

5. **Update validator**

In `fincli/config.py`, update the provider validator:

```python
@field_validator('llm_provider')
def validate_llm_provider(cls, v):
    valid = ['bedrock', 'ollama', 'openai', 'anthropic', 'gemini']
    if v not in valid:
        raise ValueError(f"Invalid provider: {v}")
    return v
```

6. **Add requirements**

```bash
echo "google-generativeai>=0.3.0" >> requirements.txt
```

### Testing

1. **Create test file**

```python
# tests/test_gemini_client.py
import pytest
from fincli.clients.gemini_client import GeminiClient


def test_gemini_text_generation():
    """Test basic text generation."""
    client = GeminiClient()
    response = client.generate_text("Say hello")
    assert len(response) > 0
    assert isinstance(response, str)


def test_gemini_json_extraction():
    """Test JSON extraction."""
    client = GeminiClient()
    prompt = """
    Extract this data as JSON:
    Name: John Doe
    Age: 30
    City: New York
    """
    result = client.extract_json(prompt)
    assert isinstance(result, dict)
    assert "name" in str(result).lower()


def test_gemini_health_check():
    """Test health check."""
    client = GeminiClient()
    assert client.health_check() is True
```

2. **Run tests**

```bash
pytest tests/test_gemini_client.py -v
```

3. **Test with CLI**

```bash
# Set in .env
FINCLI_LLM_PROVIDER=gemini
FINCLI_GEMINI_API_KEY=your-key

# Test
python cli.py chat
```

### Learning Outcomes

✅ Understand LLM client abstraction  
✅ Implement Factory pattern  
✅ Handle API integration  
✅ Write unit tests for AI components  
✅ Manage configuration

---

## 📝 Exercise 2: Implement Cache Analytics

**Objective:** Add detailed cache performance analytics

**Difficulty:** Beginner  
**Time:** 1-2 hours  
**Prerequisites:** Understanding of caching system

### Steps

1. **Create analytics module**

```python
# fincli/cache/cache_analytics.py
"""
Cache performance analytics.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict

from fincli.cache.llm_cache import LLMCache
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


class CacheAnalytics:
    """Analyze cache performance."""
    
    def __init__(self, cache: LLMCache):
        self.cache = cache
        self.hit_history: List[Dict[str, Any]] = []
        self.miss_history: List[Dict[str, Any]] = []
    
    def record_hit(self, key: str, use_case: str):
        """Record cache hit."""
        self.hit_history.append({
            'timestamp': datetime.now(),
            'key': key,
            'use_case': use_case
        })
    
    def record_miss(self, key: str, use_case: str):
        """Record cache miss."""
        self.miss_history.append({
            'timestamp': datetime.now(),
            'key': key,
            'use_case': use_case
        })
    
    def get_hit_rate(self, hours: int = 24) -> float:
        """Get cache hit rate for last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent_hits = [
            h for h in self.hit_history 
            if h['timestamp'] > cutoff
        ]
        recent_misses = [
            m for m in self.miss_history 
            if m['timestamp'] > cutoff
        ]
        
        total = len(recent_hits) + len(recent_misses)
        if total == 0:
            return 0.0
        
        return len(recent_hits) / total
    
    def get_hit_rate_by_use_case(self) -> Dict[str, float]:
        """Get hit rate broken down by use case."""
        use_case_stats = defaultdict(lambda: {'hits': 0, 'misses': 0})
        
        for hit in self.hit_history:
            use_case_stats[hit['use_case']]['hits'] += 1
        
        for miss in self.miss_history:
            use_case_stats[miss['use_case']]['misses'] += 1
        
        hit_rates = {}
        for use_case, stats in use_case_stats.items():
            total = stats['hits'] + stats['misses']
            hit_rates[use_case] = stats['hits'] / total if total > 0 else 0.0
        
        return hit_rates
    
    def get_cache_efficiency_score(self) -> float:
        """
        Calculate cache efficiency score (0-100).
        
        Factors:
        - Hit rate (50%)
        - Cache size utilization (25%)
        - Eviction rate (25%)
        """
        # Hit rate component (0-50)
        hit_rate = self.get_hit_rate()
        hit_score = hit_rate * 50
        
        # Size utilization component (0-25)
        # Optimal is 70-90% full
        cache_info = self.cache.get_cache_info()
        utilization = cache_info['size'] / cache_info['max_size']
        if 0.7 <= utilization <= 0.9:
            size_score = 25
        else:
            size_score = 25 * (1 - abs(utilization - 0.8) / 0.8)
        
        # Eviction rate component (0-25)
        # Lower eviction rate is better
        eviction_rate = cache_info.get('evictions', 0) / max(cache_info['misses'], 1)
        eviction_score = 25 * (1 - min(eviction_rate, 1.0))
        
        return hit_score + size_score + eviction_score
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations for cache optimization."""
        recommendations = []
        
        hit_rate = self.get_hit_rate()
        if hit_rate < 0.3:
            recommendations.append(
                "⚠️ Low hit rate (<30%). Consider increasing cache TTL."
            )
        
        cache_info = self.cache.get_cache_info()
        utilization = cache_info['size'] / cache_info['max_size']
        
        if utilization > 0.95:
            recommendations.append(
                "⚠️ Cache nearly full. Consider increasing max_size."
            )
        elif utilization < 0.2:
            recommendations.append(
                "💡 Cache underutilized. You could reduce max_size."
            )
        
        # Check use-case specific hit rates
        use_case_rates = self.get_hit_rate_by_use_case()
        for use_case, rate in use_case_rates.items():
            if rate < 0.2:
                recommendations.append(
                    f"⚠️ Low hit rate for {use_case} ({rate:.1%}). "
                    f"Review prompt variability."
                )
        
        if not recommendations:
            recommendations.append("✅ Cache performing well!")
        
        return recommendations
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive cache analytics report."""
        return {
            'overall_hit_rate': self.get_hit_rate(),
            'hit_rate_by_use_case': self.get_hit_rate_by_use_case(),
            'efficiency_score': self.get_cache_efficiency_score(),
            'cache_info': self.cache.get_cache_info(),
            'recommendations': self.get_recommendations(),
            'total_hits': len(self.hit_history),
            'total_misses': len(self.miss_history)
        }
```

2. **Add CLI command**

```python
# In cli.py
@app.command()
def cache_stats():
    """Show cache performance statistics."""
    from fincli.cache.cache_analytics import CacheAnalytics
    from fincli.cache.llm_cache import get_llm_cache
    
    cache = get_llm_cache()
    analytics = CacheAnalytics(cache)
    report = analytics.generate_report()
    
    console.print("\n[bold]Cache Performance Report[/bold]\n")
    
    console.print(f"Overall Hit Rate: [cyan]{report['overall_hit_rate']:.1%}[/cyan]")
    console.print(f"Efficiency Score: [cyan]{report['efficiency_score']:.1f}/100[/cyan]")
    console.print(f"Total Hits: [green]{report['total_hits']}[/green]")
    console.print(f"Total Misses: [yellow]{report['total_misses']}[/yellow]")
    
    console.print("\n[bold]Hit Rate by Use Case:[/bold]")
    for use_case, rate in report['hit_rate_by_use_case'].items():
        console.print(f"  {use_case}: {rate:.1%}")
    
    console.print("\n[bold]Recommendations:[/bold]")
    for rec in report['recommendations']:
        console.print(f"  {rec}")
```

3. **Test**

```bash
python cli.py cache-stats
```

### Learning Outcomes

✅ Implement analytics on top of existing systems  
✅ Calculate performance metrics  
✅ Generate actionable recommendations  
✅ Build CLI commands

---

## 📝 Exercise 3: Implement Prompt A/B Testing

**Objective:** Build a framework to compare prompt versions

**Difficulty:** Intermediate  
**Time:** 3-4 hours  
**Prerequisites:** Understanding of prompt management

### Steps

1. **Create A/B testing framework**

```python
# fincli/prompts/ab_testing.py
"""
A/B testing framework for prompts.
"""
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import json

from fincli.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ABTestResult:
    """Result of A/B test."""
    prompt_version: str
    success_rate: float
    avg_latency_ms: float
    avg_cost_usd: float
    total_tests: int
    errors: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'prompt_version': self.prompt_version,
            'success_rate': self.success_rate,
            'avg_latency_ms': self.avg_latency_ms,
            'avg_cost_usd': self.avg_cost_usd,
            'total_tests': self.total_tests,
            'errors': self.errors
        }


class PromptABTester:
    """A/B test different prompt versions."""
    
    def __init__(self):
        self.results: List[ABTestResult] = []
    
    def run_test(
        self,
        test_data: List[Any],
        prompt_versions: List[str],
        extraction_fn: Callable,
        validation_fn: Callable,
        category: str = "extraction",
        name: str = "transaction"
    ) -> Dict[str, ABTestResult]:
        """
        Run A/B test on multiple prompt versions.
        
        Args:
            test_data: List of test inputs
            prompt_versions: List of prompt versions to test
            extraction_fn: Function to extract data (takes version, data)
            validation_fn: Function to validate result
            category: Prompt category
            name: Prompt name
        
        Returns:
            Dictionary mapping version to results
        """
        results = {}
        
        for version in prompt_versions:
            logger.info(
                "ab_test_starting",
                version=version,
                test_count=len(test_data)
            )
            
            successes = 0
            total_latency = 0
            total_cost = 0
            errors = 0
            
            for data in test_data:
                try:
                    start = datetime.now()
                    
                    # Run extraction with this version
                    result = extraction_fn(version, data)
                    
                    # Calculate latency
                    latency_ms = (datetime.now() - start).total_seconds() * 1000
                    total_latency += latency_ms
                    
                    # Validate result
                    if validation_fn(result, data):
                        successes += 1
                    
                    # TODO: Get actual cost from metrics
                    total_cost += 0.003  # Placeholder
                    
                except Exception as e:
                    logger.error(
                        "ab_test_error",
                        version=version,
                        error=str(e)
                    )
                    errors += 1
            
            # Calculate metrics
            total_tests = len(test_data)
            success_rate = successes / total_tests if total_tests > 0 else 0
            avg_latency = total_latency / total_tests if total_tests > 0 else 0
            avg_cost = total_cost / total_tests if total_tests > 0 else 0
            
            result = ABTestResult(
                prompt_version=version,
                success_rate=success_rate,
                avg_latency_ms=avg_latency,
                avg_cost_usd=avg_cost,
                total_tests=total_tests,
                errors=errors
            )
            
            results[version] = result
            self.results.append(result)
            
            logger.info(
                "ab_test_completed",
                version=version,
                success_rate=success_rate,
                avg_latency_ms=avg_latency
            )
        
        return results
    
    def compare_versions(
        self,
        results: Dict[str, ABTestResult]
    ) -> Dict[str, Any]:
        """Compare test results and recommend best version."""
        if not results:
            return {}
        
        # Find best by different metrics
        best_accuracy = max(results.items(), key=lambda x: x[1].success_rate)
        best_speed = min(results.items(), key=lambda x: x[1].avg_latency_ms)
        best_cost = min(results.items(), key=lambda x: x[1].avg_cost_usd)
        
        # Calculate composite score (weighted)
        scores = {}
        for version, result in results.items():
            # Normalize metrics (0-1)
            max_success = max(r.success_rate for r in results.values())
            min_latency = min(r.avg_latency_ms for r in results.values())
            min_cost = min(r.avg_cost_usd for r in results.values())
            
            accuracy_score = result.success_rate / max_success if max_success > 0 else 0
            speed_score = min_latency / result.avg_latency_ms if result.avg_latency_ms > 0 else 0
            cost_score = min_cost / result.avg_cost_usd if result.avg_cost_usd > 0 else 0
            
            # Weighted composite (accuracy: 50%, speed: 25%, cost: 25%)
            composite = (accuracy_score * 0.5) + (speed_score * 0.25) + (cost_score * 0.25)
            scores[version] = composite
        
        best_overall = max(scores.items(), key=lambda x: x[1])
        
        return {
            'best_accuracy': {
                'version': best_accuracy[0],
                'success_rate': best_accuracy[1].success_rate
            },
            'best_speed': {
                'version': best_speed[0],
                'latency_ms': best_speed[1].avg_latency_ms
            },
            'best_cost': {
                'version': best_cost[0],
                'cost_usd': best_cost[1].avg_cost_usd
            },
            'best_overall': {
                'version': best_overall[0],
                'score': best_overall[1]
            },
            'recommendation': best_overall[0]
        }
    
    def export_results(self, filepath: str):
        """Export test results to JSON."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info("ab_test_results_exported", filepath=filepath)
```

2. **Create test script**

```python
# examples/ab_test_demo.py
"""
Demo of prompt A/B testing.
"""
from fincli.prompts.ab_testing import PromptABTester
from fincli.extractors.transaction_extractor import TransactionExtractor
from fincli.clients.gmail_client import EmailMessage
from datetime import datetime


# Sample test data
TEST_EMAILS = [
    {
        'subject': 'Transaction Alert',
        'body': 'Your card ending in 1234 was debited ₹500 at Starbucks on 15-Nov-2024',
        'expected': {
            'amount': 500.0,
            'merchant': 'Starbucks',
            'type': 'debit'
        }
    },
    # Add more test cases...
]


def extraction_function(version: str, email_data: dict):
    """Extract transaction using specific prompt version."""
    extractor = TransactionExtractor(prompt_version=version)
    
    # Create EmailMessage
    email = EmailMessage(
        message_id='test',
        subject=email_data['subject'],
        body=email_data['body'],
        sender='test@example.com',
        date=datetime.now()
    )
    
    return extractor.extract_from_email(email)


def validation_function(result, email_data: dict) -> bool:
    """Validate extraction result."""
    if not result or not result.is_valid():
        return False
    
    expected = email_data['expected']
    
    # Check amount
    if abs(result.amount - expected['amount']) > 0.01:
        return False
    
    # Check merchant (fuzzy match)
    if expected['merchant'].lower() not in result.merchant.lower():
        return False
    
    # Check type
    if result.transaction_type != expected['type']:
        return False
    
    return True


def main():
    """Run A/B test."""
    tester = PromptABTester()
    
    # Test versions v1 vs v2
    results = tester.run_test(
        test_data=TEST_EMAILS,
        prompt_versions=['v1', 'v2'],
        extraction_fn=extraction_function,
        validation_fn=validation_function
    )
    
    # Compare results
    comparison = tester.compare_versions(results)
    
    print("\n=== A/B Test Results ===\n")
    
    for version, result in results.items():
        print(f"{version}:")
        print(f"  Success Rate: {result.success_rate:.1%}")
        print(f"  Avg Latency: {result.avg_latency_ms:.0f}ms")
        print(f"  Avg Cost: ${result.avg_cost_usd:.4f}")
        print(f"  Errors: {result.errors}")
        print()
    
    print("=== Recommendation ===\n")
    print(f"Best Overall: {comparison['recommendation']}")
    print(f"Best Accuracy: {comparison['best_accuracy']['version']} "
          f"({comparison['best_accuracy']['success_rate']:.1%})")
    print(f"Best Speed: {comparison['best_speed']['version']} "
          f"({comparison['best_speed']['latency_ms']:.0f}ms)")
    
    # Export results
    tester.export_results('ab_test_results.json')


if __name__ == '__main__':
    main()
```

### Testing

```bash
python examples/ab_test_demo.py
```

### Learning Outcomes

✅ Implement A/B testing framework  
✅ Design evaluation metrics  
✅ Compare model/prompt performance  
✅ Make data-driven decisions

---

## 📝 Exercise 4: Add Spending Predictions

**Objective:** Predict next month's spending using simple ML

**Difficulty:** Advanced  
**Time:** 4-5 hours  
**Prerequisites:** Basic ML knowledge, pandas

### Implementation

```python
# fincli/analytics/predictions.py
"""
Spending prediction using simple ML models.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
import numpy as np

from fincli.storage.database import DatabaseManager
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


class SpendingPredictor:
    """Predict future spending patterns."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.model = None
    
    def prepare_features(
        self,
        months_back: int = 12
    ) -> pd.DataFrame:
        """
        Prepare features for prediction.
        
        Features:
        - Month number (1-12)
        - Day of week distribution
        - Average transaction size
        - Transaction count
        - Category breakdown
        """
        # Get historical transactions
        cutoff = datetime.now() - timedelta(days=months_back * 30)
        transactions = self.db.get_transactions_since(cutoff)
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'date': t.transaction_date,
                'amount': t.amount,
                'merchant': t.merchant,
                'type': t.transaction_type
            }
            for t in transactions
        ])
        
        # Group by month
        df['year_month'] = df['date'].dt.to_period('M')
        
        monthly_features = []
        
        for period in df['year_month'].unique():
            month_data = df[df['year_month'] == period]
            
            features = {
                'year_month': period,
                'month': period.month,
                'total_spending': month_data['amount'].sum(),
                'transaction_count': len(month_data),
                'avg_transaction': month_data['amount'].mean(),
                'max_transaction': month_data['amount'].max(),
                'unique_merchants': month_data['merchant'].nunique(),
            }
            
            # Day of week distribution
            day_counts = month_data['date'].dt.dayofweek.value_counts()
            for day in range(7):
                features[f'day_{day}_count'] = day_counts.get(day, 0)
            
            monthly_features.append(features)
        
        return pd.DataFrame(monthly_features)
    
    def train(self, months_back: int = 12):
        """Train prediction model."""
        df = self.prepare_features(months_back)
        
        if len(df) < 3:
            raise ValueError("Need at least 3 months of data")
        
        # Features and target
        feature_cols = [c for c in df.columns if c not in ['year_month', 'total_spending']]
        X = df[feature_cols]
        y = df['total_spending']
        
        # Train model
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X, y)
        
        # Calculate accuracy on training data
        predictions = self.model.predict(X)
        mae = np.mean(np.abs(predictions - y))
        mape = np.mean(np.abs((predictions - y) / y)) * 100
        
        logger.info(
            "prediction_model_trained",
            months=len(df),
            mae=mae,
            mape=mape
        )
        
        return {
            'mae': mae,
            'mape': mape,
            'months_trained': len(df)
        }
    
    def predict_next_month(self) -> Dict[str, float]:
        """Predict next month's spending."""
        if self.model is None:
            self.train()
        
        # Get current month features
        df = self.prepare_features(months_back=1)
        last_month = df.iloc[-1]
        
        # Prepare features for next month
        next_month = datetime.now() + timedelta(days=30)
        features = {
            'month': next_month.month,
            'transaction_count': last_month['transaction_count'],
            'avg_transaction': last_month['avg_transaction'],
            'max_transaction': last_month['max_transaction'],
            'unique_merchants': last_month['unique_merchants'],
        }
        
        # Add day distribution (use last month's pattern)
        for day in range(7):
            features[f'day_{day}_count'] = last_month[f'day_{day}_count']
        
        # Predict
        X = pd.DataFrame([features])
        prediction = self.model.predict(X)[0]
        
        # Calculate confidence interval (simple approach)
        # In production, use proper statistical methods
        std = prediction * 0.15  # Assume 15% std dev
        
        return {
            'predicted_spending': prediction,
            'lower_bound': prediction - (1.96 * std),
            'upper_bound': prediction + (1.96 * std),
            'confidence': 0.95
        }
    
    def get_spending_trend(self) -> str:
        """Analyze spending trend (increasing/decreasing/stable)."""
        df = self.prepare_features(months_back=6)
        
        if len(df) < 3:
            return "insufficient_data"
        
        # Simple linear regression on last 6 months
        X = np.arange(len(df)).reshape(-1, 1)
        y = df['total_spending'].values
        
        lr = LinearRegression()
        lr.fit(X, y)
        
        slope = lr.coef_[0]
        avg_spending = y.mean()
        
        # Classify trend
        if abs(slope) < avg_spending * 0.05:  # Less than 5% change
            return "stable"
        elif slope > 0:
            return "increasing"
        else:
            return "decreasing"
```

### Testing

```python
# Test the predictor
from fincli.analytics.predictions import SpendingPredictor
from fincli.storage.database import DatabaseManager

db = DatabaseManager()
predictor = SpendingPredictor(db)

# Train
metrics = predictor.train()
print(f"Model trained with MAPE: {metrics['mape']:.1f}%")

# Predict
prediction = predictor.predict_next_month()
print(f"Next month prediction: ₹{prediction['predicted_spending']:.2f}")
print(f"Range: ₹{prediction['lower_bound']:.2f} - ₹{prediction['upper_bound']:.2f}")

# Trend
trend = predictor.get_spending_trend()
print(f"Spending trend: {trend}")
```

### Learning Outcomes

✅ Implement ML for predictions  
✅ Feature engineering  
✅ Model training and evaluation  
✅ Confidence intervals  
✅ Trend analysis

---

## 📝 Exercise 5: Build Production Monitoring

**Objective:** Implement comprehensive monitoring with Prometheus

**Difficulty:** Advanced  
**Time:** 5-6 hours  
**Prerequisites:** Understanding of observability, Docker

### Steps

1. **Install dependencies**

```bash
pip install prometheus-client
```

2. **Create metrics module**

```python
# fincli/monitoring/prometheus_metrics.py
"""
Prometheus metrics for FinCLI.
"""
from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time

# LLM Metrics
llm_requests_total = Counter(
    'fincli_llm_requests_total',
    'Total LLM requests',
    ['provider', 'model', 'use_case', 'status']
)

llm_request_duration = Histogram(
    'fincli_llm_request_duration_seconds',
    'LLM request duration',
    ['provider', 'use_case']
)

llm_tokens_total = Counter(
    'fincli_llm_tokens_total',
    'Total tokens used',
    ['provider', 'model', 'token_type']
)

llm_cost_total = Counter(
    'fincli_llm_cost_usd_total',
    'Total LLM cost in USD',
    ['provider', 'model']
)

# Cache Metrics
cache_requests_total = Counter(
    'fincli_cache_requests_total',
    'Total cache requests',
    ['result']  # hit or miss
)

cache_size = Gauge(
    'fincli_cache_size_bytes',
    'Current cache size in bytes'
)

# Transaction Metrics
transactions_extracted_total = Counter(
    'fincli_transactions_extracted_total',
    'Total transactions extracted',
    ['status']  # success or failure
)

# Application Info
app_info = Info(
    'fincli_app',
    'Application information'
)


def track_llm_request(provider: str, model: str, use_case: str):
    """Decorator to track LLM requests."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                raise
            finally:
                duration = time.time() - start_time
                
                llm_requests_total.labels(
                    provider=provider,
                    model=model,
                    use_case=use_case,
                    status=status
                ).inc()
                
                llm_request_duration.labels(
                    provider=provider,
                    use_case=use_case
                ).observe(duration)
        
        return wrapper
    return decorator
```

3. **Add metrics endpoint to API**

```python
# In run_api.py
from prometheus_client import make_asgi_app

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

4. **Create Prometheus config**

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fincli'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

5. **Create Docker Compose for monitoring stack**

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    depends_on:
      - prometheus

volumes:
  prometheus_data:
  grafana_data:
```

6. **Start monitoring**

```bash
# Start FinCLI API
python run_api.py &

# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Access Grafana at http://localhost:3000
# Add Prometheus datasource: http://prometheus:9090
```

### Learning Outcomes

✅ Implement Prometheus metrics  
✅ Set up monitoring stack  
✅ Create dashboards  
✅ Production observability  
✅ Docker Compose

---

## 🎯 Summary

These exercises progressively build your AI engineering skills:

1. **Exercise 1:** LLM integration & abstraction
2. **Exercise 2:** Analytics & metrics
3. **Exercise 3:** A/B testing & experimentation
4. **Exercise 4:** Machine learning integration
5. **Exercise 5:** Production monitoring

**Next Steps:**
- Complete exercises in order
- Document your learnings
- Share your implementations
- Build on these foundations

Happy learning! 🚀
