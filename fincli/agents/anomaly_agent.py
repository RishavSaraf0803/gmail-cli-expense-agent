"""
AI ENGINEERING CONCEPT — The Hybrid Agent (code + LLM):

Not every agent step should use an LLM. The rule:
  - Use CODE for deterministic, mathematical, or rule-based logic
  - Use LLMs for language: explanation, synthesis, classification

This agent splits cleanly:
  STEP 1 — CODE:  statistical detection (z-scores, outlier rules)
  STEP 2 — LLM:   narrative synthesis ("here's what looks unusual")

Why not ask the LLM to find anomalies directly?
  LLMs hallucinate numbers. They cannot reliably compute "2.8 standard
  deviations above the mean" from a list of 200 transactions.
  Code computes; LLM explains. Each does what it's good at.

WHAT IS A Z-SCORE?
  z = (x - mean) / std_dev

  It measures how many standard deviations a value is from the average.
  z = 0.0  → exactly average
  z = 1.0  → one standard deviation above average
  z = 2.5  → unusually high — only ~1% of a normal distribution is above this

  Why 2.5 as the threshold? Rule of thumb for financial anomaly detection:
    z > 2.0  → flag for review (~5% of transactions, noisy)
    z > 2.5  → meaningful outlier (~1% of transactions, useful signal)
    z > 3.0  → very rare event — almost always worth reviewing

THREE DETECTION HEURISTICS (defence in depth):
  1. Category z-score   — high spend relative to your own history for that category
  2. New merchant       — merchants you've only ever used once (one-off charges)
  3. Global percentile  — top 5% by amount across ALL transactions
                          catches large charges in uncategorised or rare categories
                          where z-scores can't be computed (not enough data points)

MINIMUM SAMPLE SIZE:
  Z-scores are meaningless with fewer than 3 data points.
  With 2 transactions, std_dev is unstable; with 1, it's undefined.
  We require >= 3 transactions per category before computing z-scores.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import select

from fincli.storage.models import Transaction
from fincli.clients.base_llm_client import BaseLLMClient
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────────

Z_SCORE_THRESHOLD = 2.5       # flag transactions this many σ above category mean
MIN_CATEGORY_SAMPLE = 3       # minimum transactions per category to compute z-scores
GLOBAL_PERCENTILE = 0.95      # flag top 5% by absolute amount (global)


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class Anomaly:
    transaction: Transaction
    reason: str           # human-readable reason, e.g. "2.8σ above Food & Dining mean"
    z_score: Optional[float] = None   # set for category z-score anomalies


@dataclass
class AnomalyAgentResult:
    anomalies: List[Anomaly]
    narrative: str         # LLM-generated summary
    total_scanned: int     # total transactions analysed


# ── Prompts ────────────────────────────────────────────────────────────────────

_NARRATIVE_SYSTEM_PROMPT = """You are a personal finance analyst reviewing flagged transactions.

Given a list of statistical anomalies in a user's spending history, write a concise
3-5 sentence summary that:
- Names the most significant anomaly first (highest z-score or largest amount)
- Explains why each flagged item looks unusual (relative to their own history)
- Ends with one practical suggestion (e.g. "worth reviewing if this was intentional")

Rules:
- Only reference what's in the data — don't invent context
- Cite amounts with currency (INR) and dates
- If no anomalies: say spending looks normal"""


# ── Agent ──────────────────────────────────────────────────────────────────────

class AnomalyAgent:
    """
    Detects unusual transactions using statistical rules, then narrates findings.

    Detection is pure Python (no LLM). Narration is one LLM call.
    """

    def __init__(self, session: Session, llm: BaseLLMClient):
        self.session = session
        self.llm = llm

    def run(self, months_back: int = 3) -> AnomalyAgentResult:
        """
        Scan recent transactions for anomalies and return a narrative summary.

        Args:
            months_back: how many months of history to analyse
        """
        logger.info("anomaly_agent_start", months_back=months_back)

        # Step 1: load recent debit transactions (anomalies are spending events)
        transactions = self._load_transactions(months_back)
        if not transactions:
            return AnomalyAgentResult(
                anomalies=[],
                narrative="No transactions found to analyse.",
                total_scanned=0,
            )

        # Step 2: run all detectors
        anomalies: List[Anomaly] = []
        anomalies.extend(self._detect_category_outliers(transactions))
        anomalies.extend(self._detect_new_merchants(transactions))
        anomalies.extend(self._detect_global_large(transactions, anomalies))

        # Deduplicate (a transaction can be flagged by multiple detectors)
        seen_ids = set()
        unique_anomalies = []
        for a in anomalies:
            if a.transaction.id not in seen_ids:
                seen_ids.add(a.transaction.id)
                unique_anomalies.append(a)

        # Sort by z-score descending (highest first), then by amount
        unique_anomalies.sort(
            key=lambda a: (a.z_score or 0.0, a.transaction.amount),
            reverse=True,
        )

        logger.info(
            "anomaly_agent_detected",
            total=len(transactions),
            flagged=len(unique_anomalies),
        )

        # Step 3: LLM narrates findings
        narrative = self._narrate(unique_anomalies)

        return AnomalyAgentResult(
            anomalies=unique_anomalies,
            narrative=narrative,
            total_scanned=len(transactions),
        )

    # ── Detectors (pure Python — no LLM) ──────────────────────────────────────

    def _detect_category_outliers(self, transactions: List[Transaction]) -> List[Anomaly]:
        """
        Flag transactions where spend is Z_SCORE_THRESHOLD σ above category mean.
        Only runs for categories with >= MIN_CATEGORY_SAMPLE transactions.
        """
        by_category: dict = defaultdict(list)
        for txn in transactions:
            key = txn.category or "Uncategorised"
            by_category[key].append(txn)

        anomalies = []
        for category, txns in by_category.items():
            if len(txns) < MIN_CATEGORY_SAMPLE:
                continue

            amounts = [t.amount for t in txns]
            mean = statistics.mean(amounts)
            try:
                std = statistics.stdev(amounts)
            except statistics.StatisticsError:
                continue

            if std == 0:
                continue

            for txn in txns:
                z = (txn.amount - mean) / std
                if z >= Z_SCORE_THRESHOLD:
                    anomalies.append(Anomaly(
                        transaction=txn,
                        reason=f"{z:.1f}σ above your {category} average (mean: {mean:.0f})",
                        z_score=z,
                    ))

        return anomalies

    def _detect_new_merchants(self, transactions: List[Transaction]) -> List[Anomaly]:
        """
        Flag merchants that appear only once — one-off charges are higher risk.
        Only flags if the amount is above the median transaction amount.
        """
        merchant_counts: dict = defaultdict(int)
        for txn in transactions:
            merchant_counts[txn.merchant] += 1

        amounts = [t.amount for t in transactions]
        median_amount = statistics.median(amounts)

        anomalies = []
        for txn in transactions:
            if merchant_counts[txn.merchant] == 1 and txn.amount > median_amount:
                anomalies.append(Anomaly(
                    transaction=txn,
                    reason=f"first and only transaction at {txn.merchant}",
                ))

        return anomalies

    def _detect_global_large(
        self,
        transactions: List[Transaction],
        already_flagged: List[Anomaly],
    ) -> List[Anomaly]:
        """
        Flag transactions in the top GLOBAL_PERCENTILE by amount.
        Adds transactions not already caught by category z-score detection.
        """
        already_ids = {a.transaction.id for a in already_flagged}
        amounts = sorted(t.amount for t in transactions)
        threshold_idx = int(len(amounts) * GLOBAL_PERCENTILE)
        threshold = amounts[threshold_idx] if threshold_idx < len(amounts) else float("inf")

        anomalies = []
        for txn in transactions:
            if txn.amount >= threshold and txn.id not in already_ids:
                anomalies.append(Anomaly(
                    transaction=txn,
                    reason=f"top 5% by amount across all transactions",
                ))

        return anomalies

    # ── Synthesis (LLM) ────────────────────────────────────────────────────────

    def _narrate(self, anomalies: List[Anomaly]) -> str:
        """LLM call: anomaly list → plain-English summary."""
        if not anomalies:
            prompt = "No anomalies were detected. All spending looks within normal range."
        else:
            lines = []
            for a in anomalies[:10]:   # cap at 10 to avoid token overflow
                date_str = a.transaction.transaction_date.strftime("%Y-%m-%d")
                lines.append(
                    f"- [{date_str}] {a.transaction.currency} {a.transaction.amount:.0f} "
                    f"at {a.transaction.merchant} "
                    f"({a.transaction.category or 'Uncategorised'}) — {a.reason}"
                )
            prompt = "Flagged transactions:\n" + "\n".join(lines)

        return self.llm.generate_text(
            prompt=prompt,
            system_prompt=_NARRATIVE_SYSTEM_PROMPT,
            max_tokens=512,
            temperature=0.3,
        )

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_transactions(self, months_back: int) -> List[Transaction]:
        """Load recent debit transactions for analysis."""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=months_back * 30)
        stmt = (
            select(Transaction)
            .where(Transaction.transaction_type == "debit")
            .where(Transaction.transaction_date >= cutoff)
            .order_by(Transaction.transaction_date.desc())
        )
        return list(self.session.execute(stmt).scalars().all())
