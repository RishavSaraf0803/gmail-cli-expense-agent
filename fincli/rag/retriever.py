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
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
import numpy as np

from fincli.storage.models import Transaction
from fincli.rag.vector_store import VectorStore
from fincli.rag.embedder import OllamaEmbedder
from fincli.utils.logger import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    def __init__(self, session: Session, embedder: OllamaEmbedder):
        self.session = session
        self.embedder = embedder
        self.vector_store = VectorStore(session)

    def _extract_filters(self, query: str) -> dict:
        """
        Parse natural language hints into SQL filter parameters.

        In production systems, this step is often done with a dedicated LLM call
        (structured output / tool use) for robustness. Regex works at small scale
        and is cheaper — zero LLM tokens consumed.
        """
        filters = {}
        q = query.lower()
        now = datetime.utcnow()

        # Date windows
        if "last month" in q or "previous month" in q:
            first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0)
            last_of_prev_month = first_of_this_month - timedelta(seconds=1)
            first_of_prev_month = last_of_prev_month.replace(day=1, hour=0, minute=0, second=0)
            filters["start_date"] = first_of_prev_month
            filters["end_date"] = last_of_prev_month
        elif "this month" in q:
            filters["start_date"] = now.replace(day=1, hour=0, minute=0, second=0)
            filters["end_date"] = now
        elif "last week" in q:
            filters["start_date"] = now - timedelta(days=7)
            filters["end_date"] = now
        elif "today" in q:
            filters["start_date"] = now.replace(hour=0, minute=0, second=0)
            filters["end_date"] = now
        elif "yesterday" in q:
            yesterday = now - timedelta(days=1)
            filters["start_date"] = yesterday.replace(hour=0, minute=0, second=0)
            filters["end_date"] = yesterday.replace(hour=23, minute=59, second=59)

        # Transaction direction
        if any(w in q for w in ["spent", "debit", "paid", "purchase", "bought"]):
            filters["transaction_type"] = "debit"
        elif any(w in q for w in ["received", "credit", "refund", "income", "cashback"]):
            filters["transaction_type"] = "credit"

        # Amount threshold: "above 500", "over ₹1000", "more than 200"
        amount_match = re.search(
            r"(?:above|over|more than)\s*(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)", q
        )
        if amount_match:
            filters["min_amount"] = float(amount_match.group(1))

        return filters

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
