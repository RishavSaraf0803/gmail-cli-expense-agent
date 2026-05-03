"""
AI ENGINEERING CONCEPT — Hybrid Retrieval:

Pure semantic search on structured financial data has a critical weakness:
"how much did I spend last month?" needs exact SQL math, not approximate similarity.

The industry solution is HYBRID RETRIEVAL:
  1. SQL pre-filter  — fast, exact, handles dates/amounts/types
  2. Vector search   — semantic, handles fuzzy intent on the filtered set
  3. LLM synthesis   — reads top-K results, generates the final answer

This gives you the best of both worlds:
  - "show me food expenses last month" → SQL filters to last month's debits,
    then vector ranks by similarity to "food expenses"
  - "any suspicious charges around my Goa trip?" → vector finds contextually
    related transactions even without exact keyword matches

WHAT AI ENGINEERS CALL THIS:
  - "Pre-filtering" or "metadata filtering" for the SQL step
  - "Re-ranking" when you do a second-pass sort after initial retrieval
  - "Top-K" for the final number of documents passed to the LLM

TOP-K SIZING (practical rule of thumb):
  - Too small (K=2): LLM misses relevant context
  - Too large (K=50): LLM gets confused, slower, more expensive
  - Sweet spot: K=5–10 for most chat use cases
  - Context window math: if each transaction is ~50 tokens, K=10 = 500 tokens of context

TOOL USE UPGRADE (feature/tool-use):
  _extract_filters() was previously regex-based. It now delegates to FilterTool,
  which makes a small focused LLM call to extract structured filter parameters.

  Why pass the LLM in via __init__ instead of creating it inside the retriever?
  This is DEPENDENCY INJECTION — the caller controls which LLM is used.
  Benefits: testable (swap in a mock), flexible (use a cheap model just for
  filter extraction), no hidden globals.

  FilterTool is optional — if no LLM is provided, we fall back to empty filters
  (search all transactions). Graceful degradation beats hard failures.
"""
from typing import List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
import numpy as np

from fincli.storage.models import Transaction
from fincli.rag.vector_store import VectorStore
from fincli.rag.embedder import OllamaEmbedder
from fincli.tools.filter_tool import FilterTool
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    def __init__(
        self,
        session: Session,
        embedder: OllamaEmbedder,
        filter_tool: Optional[FilterTool] = None,
    ):
        self.session = session
        self.embedder = embedder
        self.vector_store = VectorStore(session)
        self.filter_tool = filter_tool

    def _extract_filters(self, query: str) -> dict:
        """
        Extract SQL filter parameters from the user's natural language query.

        Uses FilterTool (LLM-based) when available.
        Falls back to empty filters when no LLM is configured — retriever
        then scans all transactions, which is safe and correct, just wider.
        """
        if self.filter_tool is not None:
            return self.filter_tool.extract(query)
        return {}

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
    ) -> List[Tuple[Transaction, float]]:
        """
        Full hybrid retrieval pipeline:
          embed(query) → SQL pre-filter → cosine similarity → top-K results

        Returns list of (Transaction, similarity_score).
        The caller passes these as context to the LLM.
        """
        # Step 1: embed the user's question
        # The query and the stored transaction texts live in the same vector space —
        # that's what makes similarity meaningful.
        query_vector = self.embedder.embed(query)

        # Step 2: extract any metadata constraints
        filters = self._extract_filters(query)
        logger.info("rag_filters_extracted", filters=str(filters))

        # Step 3: SQL pre-filter for candidates
        stmt = select(Transaction)
        conditions = []

        if "start_date" in filters:
            conditions.append(Transaction.transaction_date >= filters["start_date"])
        if "end_date" in filters:
            conditions.append(Transaction.transaction_date <= filters["end_date"])
        if "transaction_type" in filters:
            conditions.append(Transaction.transaction_type == filters["transaction_type"])
        if "min_amount" in filters:
            conditions.append(Transaction.amount >= filters["min_amount"])

        if conditions:
            stmt = stmt.where(and_(*conditions))

        candidates = list(self.session.execute(stmt).scalars().all())

        # Fallback: if filters produced no results, search everything
        if not candidates:
            logger.info("rag_filter_no_results_fallback_to_all")
            candidates = list(self.session.execute(select(Transaction)).scalars().all())

        candidate_ids = [t.id for t in candidates]
        candidate_map = {t.id: t for t in candidates}

        # Step 4: rank by cosine similarity, take top-K
        scored = self.vector_store.search(query_vector, candidate_ids, top_k=top_k)

        results = [(candidate_map[tid], score) for tid, score in scored if tid in candidate_map]
        logger.info("rag_retrieval_complete", query_len=len(query), results=len(results))
        return results

    def retrieve_as_context(self, query: str, top_k: int = 8) -> str:
        """
        Convenience method: retrieves and formats results as a prompt context string.
        This is what gets injected into the LLM prompt.
        """
        results = self.retrieve(query, top_k=top_k)
        if not results:
            return "No relevant transactions found."

        lines = []
        for txn, score in results:
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
