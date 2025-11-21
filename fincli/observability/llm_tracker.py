"""
LLM Metrics Tracker for monitoring costs, performance, and reliability.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from collections import defaultdict

from fincli.utils.logger import get_logger
from fincli.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


# Cost per 1K tokens (approximate, as of Nov 2024)
PROVIDER_COSTS = {
    "anthropic": {
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
        "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    },
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    },
    "bedrock": {
        "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.00025, "output": 0.00125},
    },
    "ollama": {
        "default": {"input": 0.0, "output": 0.0}  # Free local models
    }
}


@dataclass
class LLMCallMetrics:
    """Metrics for a single LLM call."""
    timestamp: str
    provider: str
    model: str
    use_case: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    success: bool
    error_message: Optional[str] = None
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class LLMMetricsTracker:
    """
    Track and analyze LLM usage metrics.

    Features:
    - Token usage tracking (input/output)
    - Cost calculation per provider
    - Latency monitoring
    - Success/failure rates
    - Use-case breakdown
    - Historical data persistence
    """

    def __init__(self, metrics_file: Optional[Path] = None):
        """
        Initialize metrics tracker.

        Args:
            metrics_file: Path to store metrics. Defaults to fincli_metrics.jsonl
        """
        self.metrics_file = metrics_file or Path("fincli_metrics.jsonl")
        self.metrics: List[LLMCallMetrics] = []
        self._load_metrics()
        logger.info("llm_metrics_tracker_initialized", file=str(self.metrics_file))

    def _load_metrics(self):
        """Load existing metrics from file."""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self.metrics.append(LLMCallMetrics(**data))
                logger.info("metrics_loaded", count=len(self.metrics))
            except Exception as e:
                logger.error("metrics_load_failed", error=str(e))

    def _calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost in USD for a call.

        Args:
            provider: Provider name
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Get provider costs
        provider_pricing = PROVIDER_COSTS.get(provider, {})

        # Find matching model pricing
        model_pricing = None
        for model_name, pricing in provider_pricing.items():
            if model_name in model or model_name == "default":
                model_pricing = pricing
                break

        if not model_pricing:
            logger.warning(
                "pricing_not_found",
                provider=provider,
                model=model
            )
            return 0.0

        # Calculate cost (pricing is per 1K tokens)
        input_cost = (input_tokens / 1000.0) * model_pricing["input"]
        output_cost = (output_tokens / 1000.0) * model_pricing["output"]

        return round(input_cost + output_cost, 6)

    def track_call(
        self,
        provider: str,
        model: str,
        use_case: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        success: bool,
        error_message: Optional[str] = None
    ) -> LLMCallMetrics:
        """
        Track a single LLM call.

        Args:
            provider: Provider name (anthropic, openai, bedrock, ollama)
            model: Model identifier
            use_case: Use case (extraction, chat, summary, analysis)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Latency in milliseconds
            success: Whether the call succeeded
            error_message: Error message if failed

        Returns:
            LLMCallMetrics object
        """
        cost = self._calculate_cost(provider, model, input_tokens, output_tokens)

        metrics = LLMCallMetrics(
            timestamp=datetime.now().isoformat(),
            provider=provider,
            model=model,
            use_case=use_case,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
            cost_usd=cost
        )

        self.metrics.append(metrics)
        self._persist_metric(metrics)

        logger.info(
            "llm_call_tracked",
            provider=provider,
            use_case=use_case,
            tokens=input_tokens + output_tokens,
            cost_usd=cost,
            success=success
        )

        return metrics

    def _persist_metric(self, metric: LLMCallMetrics):
        """Persist a single metric to file."""
        try:
            with open(self.metrics_file, 'a') as f:
                f.write(json.dumps(metric.to_dict()) + '\n')
        except Exception as e:
            logger.error("metric_persist_failed", error=str(e))

    def get_total_cost(
        self,
        provider: Optional[str] = None,
        use_case: Optional[str] = None,
        start_date: Optional[datetime] = None
    ) -> float:
        """
        Get total cost in USD.

        Args:
            provider: Filter by provider
            use_case: Filter by use case
            start_date: Filter by start date

        Returns:
            Total cost in USD
        """
        filtered = self._filter_metrics(provider, use_case, start_date)
        return sum(m.cost_usd for m in filtered)

    def get_total_tokens(
        self,
        provider: Optional[str] = None,
        use_case: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Get total token usage.

        Args:
            provider: Filter by provider
            use_case: Filter by use case

        Returns:
            Dict with input_tokens, output_tokens, total_tokens
        """
        filtered = self._filter_metrics(provider, use_case)

        input_tokens = sum(m.input_tokens for m in filtered)
        output_tokens = sum(m.output_tokens for m in filtered)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }

    def get_success_rate(
        self,
        provider: Optional[str] = None,
        use_case: Optional[str] = None
    ) -> float:
        """
        Get success rate as percentage.

        Args:
            provider: Filter by provider
            use_case: Filter by use case

        Returns:
            Success rate (0.0 to 1.0)
        """
        filtered = self._filter_metrics(provider, use_case)

        if not filtered:
            return 0.0

        successful = sum(1 for m in filtered if m.success)
        return successful / len(filtered)

    def get_latency_stats(
        self,
        provider: Optional[str] = None,
        use_case: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get latency statistics.

        Args:
            provider: Filter by provider
            use_case: Filter by use case

        Returns:
            Dict with p50, p95, p99, mean, max
        """
        filtered = self._filter_metrics(provider, use_case)

        if not filtered:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "max": 0.0
            }

        latencies = sorted([m.latency_ms for m in filtered])
        count = len(latencies)

        return {
            "p50": latencies[int(count * 0.5)],
            "p95": latencies[int(count * 0.95)] if count > 20 else latencies[-1],
            "p99": latencies[int(count * 0.99)] if count > 100 else latencies[-1],
            "mean": sum(latencies) / count,
            "max": latencies[-1]
        }

    def get_cost_by_provider(self) -> Dict[str, float]:
        """
        Get cost breakdown by provider.

        Returns:
            Dict mapping provider to total cost
        """
        costs = defaultdict(float)
        for metric in self.metrics:
            costs[metric.provider] += metric.cost_usd
        return dict(costs)

    def get_cost_by_use_case(self) -> Dict[str, float]:
        """
        Get cost breakdown by use case.

        Returns:
            Dict mapping use case to total cost
        """
        costs = defaultdict(float)
        for metric in self.metrics:
            costs[metric.use_case] += metric.cost_usd
        return dict(costs)

    def get_summary_report(self, include_cache_stats: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive summary report.

        Args:
            include_cache_stats: Include cache statistics if available

        Returns:
            Dict with all key metrics
        """
        total_calls = len(self.metrics)
        successful_calls = sum(1 for m in self.metrics if m.success)

        report = {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "success_rate": self.get_success_rate(),
            "total_cost_usd": self.get_total_cost(),
            "cost_by_provider": self.get_cost_by_provider(),
            "cost_by_use_case": self.get_cost_by_use_case(),
            "total_tokens": self.get_total_tokens(),
            "latency_stats": self.get_latency_stats(),
            "providers_used": list(set(m.provider for m in self.metrics)),
            "use_cases": list(set(m.use_case for m in self.metrics))
        }

        # Include cache stats if requested
        if include_cache_stats:
            try:
                from fincli.cache import get_cache_manager
                cache_manager = get_cache_manager()
                cache_stats = cache_manager.get_stats()
                report["cache_stats"] = cache_stats.to_dict()
            except Exception as e:
                logger.debug("cache_stats_unavailable", error=str(e))
                report["cache_stats"] = None

        return report

    def _filter_metrics(
        self,
        provider: Optional[str] = None,
        use_case: Optional[str] = None,
        start_date: Optional[datetime] = None
    ) -> List[LLMCallMetrics]:
        """Filter metrics by criteria."""
        filtered = self.metrics

        if provider:
            filtered = [m for m in filtered if m.provider == provider]

        if use_case:
            filtered = [m for m in filtered if m.use_case == use_case]

        if start_date:
            filtered = [
                m for m in filtered
                if datetime.fromisoformat(m.timestamp) >= start_date
            ]

        return filtered

    def export_to_json(self, output_file: Path):
        """
        Export all metrics to JSON file.

        Args:
            output_file: Path to output file
        """
        data = {
            "summary": self.get_summary_report(),
            "metrics": [m.to_dict() for m in self.metrics]
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info("metrics_exported", file=str(output_file))

    def clear_metrics(self):
        """Clear all metrics (use with caution)."""
        self.metrics = []
        if self.metrics_file.exists():
            self.metrics_file.unlink()
        logger.warning("metrics_cleared")


# Global singleton instance
_metrics_tracker: Optional[LLMMetricsTracker] = None


def get_metrics_tracker() -> LLMMetricsTracker:
    """
    Get LLM metrics tracker (singleton pattern).

    Returns:
        Configured LLMMetricsTracker instance
    """
    global _metrics_tracker

    if _metrics_tracker is None:
        _metrics_tracker = LLMMetricsTracker()
        logger.info("metrics_tracker_singleton_created")

    return _metrics_tracker


def reset_metrics_tracker():
    """Reset the global metrics tracker instance (for testing)."""
    global _metrics_tracker
    _metrics_tracker = None
    logger.info("metrics_tracker_reset")
