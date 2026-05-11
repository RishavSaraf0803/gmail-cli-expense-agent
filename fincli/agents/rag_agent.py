"""
AI ENGINEERING CONCEPT — The Agentic Loop:

A pipeline always follows the same fixed steps regardless of output quality.
An agent observes its own output, evaluates it, and can change strategy.

The difference in code:
  Pipeline: retrieve → format → answer        (no branching)
  Agent:    retrieve → score → good enough?
              yes → answer
              no  → rephrase → retrieve again → answer

RAGAgent implements this as the simplest possible agentic loop:
  retrieve → check best similarity score → if below threshold → rephrase → retry

WHAT IS A SIMILARITY SCORE?
  Cosine similarity between the query vector and each stored transaction vector.
  Ranges 0–1 for well-behaved embedding models.

  Rule of thumb for financial transaction text:
    > 0.50  strong match — document is clearly about this topic
    0.35–0.50  decent — relevant but may not be exactly on point
    < 0.35  weak — the retriever is guessing; worth rephrasing

WHY DO LOW SCORES HAPPEN?
  Transaction text looks like: "DEBIT INR 850.00 at Zomato (Food & Dining)"
  User asks: "what did I eat?"
  The embedding model can't find overlap — different vocabulary entirely.

  Rephrased: "food and dining expenses at restaurants and delivery apps"
  Now the vocabulary overlaps — cosine similarity jumps.

  This is a lightweight form of QUERY EXPANSION. The full version is HyDE
  (Hypothetical Document Embedding): generate a fake ideal answer, embed it,
  use it as the search vector. We do the cheaper variant: expand the question.

ONE RETRY ONLY:
  If two different phrasings both score low, the problem is usually missing data,
  not a phrasing mismatch. More retries burn tokens without improving results.

SYNTHESIS LIVES IN THE AGENT, NOT THE CALLER:
  The old chat command built the LLM prompt inline. Moving it here makes the
  agent self-contained — the caller just gets an answer back. This is why agents
  are composable: the orchestrator doesn't need to know how RAG works internally.
"""
from dataclasses import dataclass
from typing import List, Tuple

from fincli.rag.retriever import HybridRetriever
from fincli.storage.models import Transaction
from fincli.clients.base_llm_client import BaseLLMClient
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

# Cosine similarity below this triggers a rephrase attempt
SCORE_THRESHOLD = 0.35

_REPHRASE_SYSTEM_PROMPT = """You are a query rewriter for a personal finance search engine.

The user's question did not return strong matches from the transaction database.
Rewrite it using finance-domain vocabulary so it matches stored transaction text better.

Transaction text looks like: "DEBIT INR 850 at Zomato (Food & Dining) via Credit Card"
Use terms like: debit, credit, merchant, expense, payment, category names
(Food & Dining, Travel, Shopping, Entertainment, Utilities, Healthcare)

Return ONLY the rewritten query — no explanation, no quotes, one line."""

_SYNTHESIS_SYSTEM_PROMPT = """You are FinCLI, a helpful personal finance assistant.
Answer the user's question using ONLY the transaction data provided.
If the data doesn't contain enough information, say so honestly.
Be concise. When citing amounts, include the currency and date."""


@dataclass
class RAGAgentResult:
    question: str       # original user question
    final_query: str    # query actually used for retrieval (may be rephrased)
    answer: str         # LLM-synthesized answer
    rephrased: bool = False   # True if a rephrase+retry was triggered
    result_count: int = 0     # number of transactions retrieved


class RAGAgent:
    """
    Self-correcting RAG agent.

    Wraps HybridRetriever with a quality-check loop:
    if retrieval scores are weak, rephrases the query and retries once.
    Synthesizes a final answer from whichever retrieval scored better.
    """

    def __init__(self, retriever: HybridRetriever, llm: BaseLLMClient):
        self.retriever = retriever
        self.llm = llm

    def run(self, question: str, top_k: int = 8) -> RAGAgentResult:
        """
        Full pipeline: retrieve → evaluate → (maybe) rephrase+retry → synthesize.
        Always returns a RAGAgentResult.
        """
        logger.info("rag_agent_start", question=question[:80])

        # Step 1: initial retrieval
        results = self.retriever.retrieve(question, top_k=top_k)
        best_score = _best_score(results)
        final_query = question
        rephrased = False

        logger.info("rag_agent_initial_retrieval", results=len(results), best_score=round(best_score, 3))

        # Step 2: evaluate — if weak, rephrase and retry
        if best_score < SCORE_THRESHOLD:
            logger.info("rag_agent_low_score_rephrasing", threshold=SCORE_THRESHOLD)
            rephrased_query = self._rephrase(question)

            if rephrased_query:
                retry_results = self.retriever.retrieve(rephrased_query, top_k=top_k)
                retry_score = _best_score(retry_results)

                logger.info(
                    "rag_agent_retry",
                    rephrased_query=rephrased_query[:80],
                    retry_score=round(retry_score, 3),
                )

                # Only use the rephrased results if they actually scored better
                if retry_score > best_score:
                    results = retry_results
                    best_score = retry_score
                    final_query = rephrased_query
                    rephrased = True

        # Step 3: format context for the LLM
        context = _format_context(results)

        # Step 4: synthesize answer
        answer = self._synthesize(question, context)

        logger.info("rag_agent_complete", rephrased=rephrased, result_count=len(results))

        return RAGAgentResult(
            question=question,
            final_query=final_query,
            answer=answer,
            rephrased=rephrased,
            result_count=len(results),
        )

    def _rephrase(self, question: str) -> str:
        """Ask the LLM to rewrite the query with finance-domain vocabulary."""
        try:
            rephrased = self.llm.generate_text(
                prompt=question,
                system_prompt=_REPHRASE_SYSTEM_PROMPT,
                max_tokens=128,
                temperature=0.5,
            ).strip()
            return rephrased if rephrased != question else ""
        except Exception as e:
            logger.warning("rag_agent_rephrase_failed", error=str(e))
            return ""

    def _synthesize(self, question: str, context: str) -> str:
        """LLM call: raw transaction context → natural language answer."""
        prompt = f"""Relevant Transactions:
{context}

User: {question}
Answer:"""
        return self.llm.generate_text(
            prompt=prompt,
            system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.3,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _best_score(results: List[Tuple[Transaction, float]]) -> float:
    """Return the highest similarity score from a retrieval result set."""
    if not results:
        return 0.0
    return max(score for _, score in results)


def _format_context(results: List[Tuple[Transaction, float]]) -> str:
    """Format retrieved transactions as a readable context string for the LLM."""
    if not results:
        return "No relevant transactions found."
    lines = []
    for txn, _ in results:
        date_str = txn.transaction_date.strftime("%Y-%m-%d")
        line = (
            f"- [{date_str}] {txn.transaction_type.upper()} "
            f"{txn.currency} {txn.amount} at {txn.merchant}"
        )
        if txn.category:
            line += f" ({txn.category})"
        if txn.payment_method:
            line += f" via {txn.payment_method}"
        lines.append(line)
    return "\n".join(lines)
