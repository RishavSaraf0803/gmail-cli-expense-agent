"""
AI ENGINEERING CONCEPT — Tool Use via Structured Output:

A "tool" in LLM terms is a function the LLM can decide to call.
The LLM doesn't execute it — it emits structured arguments, and YOUR code runs it.

The flow:
  1. You describe the tool in the system prompt (name, purpose, parameter schema)
  2. LLM reads the user's question and decides what args to fill in
  3. LLM returns structured JSON (the "tool call")
  4. You validate the args and execute the actual logic

WHY this beats regex:
  - Regex: `"last month"` only. LLM: understands "April", "Q1", "past 30 days", "since my trip"
  - Regex: brittle on typos/synonyms. LLM: handles "expenditures", "charges", "outgoing"
  - Regex: can only extract what you anticipated. LLM: generalises to unseen phrasings

THIS IS THE SAME CONCEPT AS NATIVE TOOL USE (Anthropic/OpenAI):
  - Native tool use: provider enforces the schema, returns a `tool_use` block
  - Structured output (what we do here): you describe the schema in the prompt,
    LLM returns JSON, you validate with Pydantic
  - The LLM's reasoning is identical — only the transport mechanism differs.
  - Native tool use adds: schema enforcement, explicit tool_use/tool_result turns.
  - Structured output adds: works across ALL providers with a single code path.

PRODUCTION NOTE:
  In high-stakes systems (financial actions, API calls), always use native tool use
  so the provider guarantees schema conformance. For read-only filter extraction
  like this, structured output is fine — a bad parse just means a wider SQL scan.
"""
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────────
# Pydantic model doubles as documentation for the LLM (we serialize it into
# the system prompt) and as a validator for the LLM's output.

class TransactionFilters(BaseModel):
    """
    Structured filters the LLM extracts from a natural language query.
    All fields are optional — LLM only fills what the question implies.
    """
    start_date: Optional[str] = None   # ISO 8601: "2026-04-01"
    end_date: Optional[str] = None     # ISO 8601: "2026-04-30"
    transaction_type: Optional[str] = None  # "debit" | "credit" | null
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

    @field_validator("transaction_type")
    @classmethod
    def validate_txn_type(cls, v):
        if v is not None and v not in ("debit", "credit"):
            return None
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, v):
        if v is None:
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            return None

    def to_datetime_dict(self) -> dict:
        """Convert string dates to datetime objects for SQL queries."""
        result = {}
        if self.start_date:
            result["start_date"] = datetime.strptime(self.start_date, "%Y-%m-%d")
        if self.end_date:
            # End of day so the range is inclusive
            result["end_date"] = datetime.strptime(self.end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        if self.transaction_type:
            result["transaction_type"] = self.transaction_type
        if self.min_amount is not None:
            result["min_amount"] = self.min_amount
        if self.max_amount is not None:
            result["max_amount"] = self.max_amount
        return result


# ── Tool definition (what the LLM sees) ───────────────────────────────────────
# In native tool use (Anthropic/OpenAI), this is the `tools` parameter.
# Here we embed it in the system prompt — same information, different transport.

_TOOL_SYSTEM_PROMPT = f"""You are a filter extraction tool for a personal finance app.
Today's date is {{today}}.

Your job: read the user's question and extract SQL filter parameters as JSON.
Only include fields that the question explicitly implies. Use null for everything else.

Return ONLY valid JSON matching this schema — no explanation, no markdown:
{{
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "transaction_type": "debit | credit | null",
  "min_amount": "number or null",
  "max_amount": "number or null"
}}

Rules:
- "last month" → first and last day of the previous calendar month
- "this month" → first day of current month to today
- "last week"  → 7 days ago to today
- "this year"  → Jan 1 of current year to today
- "spent / paid / bought / debit" → transaction_type: "debit"
- "received / credited / refund / cashback" → transaction_type: "credit"
- "above X / over X / more than X" → min_amount: X
- "below X / under X / less than X" → max_amount: X
- If no time window is mentioned, set both dates to null
- Never invent filters the question doesn't imply
"""


# ── Extractor ─────────────────────────────────────────────────────────────────

class FilterTool:
    """
    Uses an LLM to extract structured transaction filters from natural language.

    Drop-in replacement for regex-based filter extraction.
    Falls back to empty filters (search everything) if the LLM call fails —
    the retriever handles no-filter gracefully.
    """

    def __init__(self, llm: BaseLLMClient):
        self.llm = llm

    def extract(self, query: str) -> dict:
        """
        Extract filter parameters from a natural language query.

        Returns a dict ready for use as SQL filter kwargs —
        same shape as the old regex-based _extract_filters() output.
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        system_prompt = _TOOL_SYSTEM_PROMPT.format(today=today)

        try:
            raw = self.llm.extract_json(
                prompt=query,
                system_prompt=system_prompt,
                max_tokens=256,
            )
            filters = TransactionFilters(**raw)
            result = filters.to_datetime_dict()
            logger.info("filter_tool_extracted", query_snippet=query[:60], filters=str(result))
            return result

        except Exception as e:
            # Bad LLM output or network failure — safe fallback: no filters = search all
            logger.warning("filter_tool_failed_fallback", error=str(e))
            return {}
