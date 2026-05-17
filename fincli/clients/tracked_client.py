"""
TrackedLLMClient — decorator that wires CircuitBreaker + LLMMetricsTracker
around any BaseLLMClient without modifying the underlying client code.

Layering in production code (outermost → innermost):
  LLMCache → TrackedLLMClient → CircuitBreaker → raw provider client

  LLMCache:         skip API if we've seen this exact prompt before
  TrackedLLMClient: time the call, record tokens/latency/cost, trip the breaker
  CircuitBreaker:   stop calling a provider that has failed N times in a row
  raw client:       actually talks to Anthropic / OpenAI / Ollama / Bedrock

WHY MEASURE AT THIS LAYER, NOT IN THE RAW CLIENTS?
  The raw clients (AnthropicClient, OllamaClient, …) are provider-specific.
  Tracking inside each one duplicates the instrumentation logic 4 times.
  One wrapper here instruments ALL providers with a single implementation.
  This is the "decorator pattern" — behaviour added without subclassing.

TOKEN ESTIMATION:
  Exact token counts require calling the provider's tokenizer.
  We estimate with ~4 chars/token (GPT/Claude rule of thumb).
  Good enough for cost tracking and alerting — exact enough to spot
  a prompt that's 10x more expensive than expected.
"""
import time
from typing import Optional, Dict, Any

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.observability.llm_tracker import get_metrics_tracker
from fincli.resilience.circuit_breaker import get_circuit_breaker
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


def _infer_provider(client: BaseLLMClient) -> str:
    """Derive provider name from class name — avoids adding provider_name to every client."""
    class_name = type(client).__name__.lower()
    for known in ("anthropic", "ollama", "openai", "bedrock"):
        if known in class_name:
            return known
    return class_name.replace("client", "") or "unknown"


def _estimate_tokens(*texts: Optional[str]) -> int:
    """Rough token estimate: ~4 characters per token (GPT/Claude rule of thumb)."""
    total = sum(len(t) for t in texts if t)
    return max(1, total // 4)


class TrackedLLMClient(BaseLLMClient):
    """
    Drop-in wrapper for any BaseLLMClient.

    Adds circuit breaker protection, latency measurement, and metrics tracking
    without changing a single line in the underlying provider clients.
    """

    def __init__(self, client: BaseLLMClient, use_case: str):
        self._client = client
        self._use_case = use_case
        self._provider = _infer_provider(client)
        self._model = getattr(client, "model_name", "unknown")
        self._tracker = get_metrics_tracker()
        self._circuit_breaker = get_circuit_breaker(f"llm-{self._provider}")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        start = time.monotonic()
        try:
            result = self._circuit_breaker.call(
                self._client.generate_text,
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            self._tracker.track_call(
                provider=self._provider,
                model=self._model,
                use_case=self._use_case,
                input_tokens=_estimate_tokens(prompt, system_prompt),
                output_tokens=_estimate_tokens(result),
                latency_ms=(time.monotonic() - start) * 1000,
                success=True,
            )
            return result
        except Exception as e:
            self._tracker.track_call(
                provider=self._provider,
                model=self._model,
                use_case=self._use_case,
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.monotonic() - start) * 1000,
                success=False,
                error_message=str(e),
            )
            raise

    def extract_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            result = self._circuit_breaker.call(
                self._client.extract_json,
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
            self._tracker.track_call(
                provider=self._provider,
                model=self._model,
                use_case=self._use_case,
                input_tokens=_estimate_tokens(prompt, system_prompt),
                output_tokens=_estimate_tokens(str(result)),
                latency_ms=(time.monotonic() - start) * 1000,
                success=True,
            )
            return result
        except Exception as e:
            self._tracker.track_call(
                provider=self._provider,
                model=self._model,
                use_case=self._use_case,
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.monotonic() - start) * 1000,
                success=False,
                error_message=str(e),
            )
            raise

    def health_check(self) -> bool:
        return self._client.health_check()
