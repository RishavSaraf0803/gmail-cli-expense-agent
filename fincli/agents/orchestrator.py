"""
AI ENGINEERING CONCEPT — The Orchestrator Pattern:

An orchestrator is a meta-agent: it doesn't answer the question itself.
It classifies intent, routes to the right specialist, and merges results.

  User question
        ↓
   Orchestrator  (LLM call 1: classify)
        ↓
   route = "sql" | "rag" | "both"
        ↓           ↓           ↓
   SQLAgent    RAGAgent     both →  merge (LLM call 2)

WHY ROUTING MATTERS:
  SQL and RAG are complements, not substitutes.
  "how much did I spend on food last month?"
    → SQL: SELECT SUM(amount) ... WHERE category LIKE '%Food%'   (exact answer)
    → RAG: retrieves food transactions by similarity              (context)
  Neither alone is ideal. SQL gives the number. RAG gives examples.
  The orchestrator picks the right tool — or both — based on the question.

HOW WE CLASSIFY (LLM-based routing):
  We describe the two tools and ask the LLM to pick one.
  Output is ONE word: "sql", "rag", or "both".
  Why LLM and not keyword matching?
    Keyword: "how much" → sql, "show me" → rag — brittle.
    LLM: understands "any chance I overpaid?" = semantic = rag.
    LLM: understands "average weekly spend" = aggregate = sql.
  The routing LLM call is cheap (tiny output, temperature=0.0).

THE MERGE STEP:
  When route = "both", we run both agents sequentially and pass both answers
  to a third LLM call that synthesizes a single coherent response.
  This is "answer fusion" — a common pattern in multi-agent systems.

  Why a third LLM call and not just concatenating the two answers?
  Concatenation forces the user to reconcile two responses mentally.
  The merge LLM produces one answer that uses both as grounding.

SEQUENTIAL VS PARALLEL EXECUTION:
  We run agents sequentially here (simpler, easier to reason about).
  Production systems run them in parallel (asyncio.gather or threads)
  to cut latency — the two agents don't depend on each other's output.
  Sequential is correct. Parallel is an optimization.
"""
from dataclasses import dataclass, field
from typing import Optional

from fincli.agents.sql_agent import SQLAgent, SQLAgentResult
from fincli.agents.rag_agent import RAGAgent, RAGAgentResult
from fincli.clients.base_llm_client import BaseLLMClient
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

# ── Routing ────────────────────────────────────────────────────────────────────

_ROUTER_SYSTEM_PROMPT = """You are a query router for a personal finance assistant.

You have two tools available:
  sql  — for exact, aggregate, or comparative queries
         Use when: totals, averages, counts, top-N, date ranges, "how much", "how many"
         Examples: "how much did I spend last month?", "top 5 merchants", "compare April vs May"

  rag  — for semantic, fuzzy, or contextual queries
         Use when: finding specific kinds of transactions, looking for patterns, "show me"
         Examples: "any suspicious charges?", "what did I eat?", "transactions near my Goa trip"

  both — when the question needs exact data AND semantic context
         Examples: "is my food spending unusually high?", "compare travel to normal months"

Rules:
- Default to "sql" when the question has numbers, aggregates, or time comparisons
- Default to "rag" when the question is fuzzy, contextual, or pattern-based
- Use "both" sparingly — only when the question genuinely needs both
- Respond with EXACTLY one word: sql, rag, or both"""

_MERGE_SYSTEM_PROMPT = """You are a personal finance assistant synthesizing two analysis results.

You have been given:
1. A structured SQL analysis (exact numbers, aggregates)
2. A semantic RAG analysis (relevant transactions, context)

Combine them into ONE coherent answer. Lead with the most useful insight.
Use the SQL result for any numbers. Use the RAG result for context and examples.
Be concise — 3-5 sentences maximum. Do not repeat the question."""


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    question: str
    route: str                              # "sql" | "rag" | "both"
    answer: str                             # final answer shown to user
    sql_result: Optional[SQLAgentResult] = None
    rag_result: Optional[RAGAgentResult] = None
    error: Optional[str] = None


# ── Agent ──────────────────────────────────────────────────────────────────────

class OrchestratorAgent:
    """
    Routes questions to the right specialist agent and merges results.

    Requires both SQLAgent and RAGAgent to be pre-constructed and injected.
    The orchestrator itself does not know about databases or embedders —
    it only speaks to agents.
    """

    def __init__(
        self,
        llm: BaseLLMClient,
        sql_agent: SQLAgent,
        rag_agent: RAGAgent,
    ):
        self.llm = llm
        self.sql_agent = sql_agent
        self.rag_agent = rag_agent

    def run(self, question: str) -> OrchestratorResult:
        """Classify → route → (merge) → return."""
        logger.info("orchestrator_start", question=question[:80])

        # Step 1: classify intent
        route = self._classify(question)
        logger.info("orchestrator_routed", route=route)

        # Step 2: execute the chosen path
        if route == "sql":
            return self._run_sql(question)
        elif route == "rag":
            return self._run_rag(question)
        else:
            return self._run_both(question)

    # ── Routing ────────────────────────────────────────────────────────────────

    def _classify(self, question: str) -> str:
        """LLM call 1: classify question intent → 'sql', 'rag', or 'both'."""
        raw = self.llm.generate_text(
            prompt=question,
            system_prompt=_ROUTER_SYSTEM_PROMPT,
            max_tokens=8,
            temperature=0.0,
        ).strip().lower()

        # Normalise — LLM may return "sql." or "SQL" despite instructions
        for token in ("sql", "rag", "both"):
            if token in raw:
                return token

        logger.warning("orchestrator_classify_fallback", raw=raw)
        return "rag"  # safe default: RAG degrades more gracefully than SQL

    # ── Execution paths ────────────────────────────────────────────────────────

    def _run_sql(self, question: str) -> OrchestratorResult:
        result = self.sql_agent.run(question)
        error = result.error if result.error else None
        return OrchestratorResult(
            question=question,
            route="sql",
            answer=result.answer,
            sql_result=result,
            error=error,
        )

    def _run_rag(self, question: str) -> OrchestratorResult:
        result = self.rag_agent.run(question)
        return OrchestratorResult(
            question=question,
            route="rag",
            answer=result.answer,
            rag_result=result,
        )

    def _run_both(self, question: str) -> OrchestratorResult:
        """Run both agents sequentially, then merge their answers."""
        sql_result = self.sql_agent.run(question)
        rag_result = self.rag_agent.run(question)

        merged = self._merge(question, sql_result.answer, rag_result.answer)

        return OrchestratorResult(
            question=question,
            route="both",
            answer=merged,
            sql_result=sql_result,
            rag_result=rag_result,
        )

    def _merge(self, question: str, sql_answer: str, rag_answer: str) -> str:
        """LLM call 2: combine SQL and RAG answers into one coherent response."""
        prompt = f"""Question: {question}

SQL analysis:
{sql_answer}

Semantic analysis:
{rag_answer}"""

        return self.llm.generate_text(
            prompt=prompt,
            system_prompt=_MERGE_SYSTEM_PROMPT,
            max_tokens=512,
            temperature=0.3,
        )
