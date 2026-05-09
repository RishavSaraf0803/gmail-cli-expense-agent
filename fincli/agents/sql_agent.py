"""
AI ENGINEERING CONCEPT — The SQL Agent:

An agent is a unit that:
  1. Receives a goal in natural language
  2. Decides HOW to achieve it (which actions to take)
  3. Executes those actions
  4. Returns a result

This SQL agent achieves goals that RAG cannot:
  RAG: "find transactions similar to food"   → fuzzy, semantic
  SQL: "sum all debits in April grouped by category" → exact, deterministic

The two-LLM-call pattern:
  Call 1 — PLAN:    LLM reads the schema + question → writes a SQL query
  Call 2 — PRESENT: LLM reads the raw rows → writes a human answer

  Why two calls? The first LLM doesn't know the results yet.
  You can't ask "what does this data mean?" before you have the data.
  This sequence (plan → execute → interpret) is the atomic unit of every agent.

SAFETY — why we enforce SELECT-only in CODE, not just in the prompt:
  Prompts are suggestions. Code is law.
  If the LLM hallucinates a DELETE or the prompt is injected via user input,
  the code guard is the last line of defence. Never rely solely on the prompt
  to prevent destructive actions when you control the execution layer.

RETRY LOGIC:
  SQL syntax errors are common on first generation — the LLM may not know
  SQLite-specific syntax (e.g. strftime vs DATE_TRUNC). We feed the error
  back: "that query failed with X, try again." One retry is almost always
  enough; more retries rarely help and burn tokens.

TEXT-TO-SQL IN PRODUCTION:
  Production systems add: query caching, query plan analysis, result size
  limits (LIMIT N), and sometimes a "query validator" LLM pass before
  execution. For learning purposes, we keep it to: generate → validate →
  execute → retry once → synthesize.
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from fincli.clients.base_llm_client import BaseLLMClient
from fincli.utils.logger import get_logger

logger = get_logger(__name__)

# ── Schema definition (what the LLM sees) ─────────────────────────────────────
# Giving the LLM the exact column names and types is critical.
# Without this, it guesses — and it will use "date" instead of
# "transaction_date", or "type" instead of "transaction_type".

_SCHEMA = """
Table: transactions
Columns:
  id                INTEGER  PRIMARY KEY
  amount            REAL     transaction amount (always positive)
  transaction_type  TEXT     'debit' (money out) or 'credit' (money in)
  merchant          TEXT     merchant or source name
  currency          TEXT     currency code, default 'INR'
  transaction_date  DATETIME format: 'YYYY-MM-DD HH:MM:SS'
  category          TEXT     nullable — e.g. 'Food & Dining', 'Shopping', 'Travel'
  payment_method    TEXT     nullable — e.g. 'Credit Card', 'UPI', 'Cash'
  email_subject     TEXT     nullable — original email subject
  notes             TEXT     nullable
  created_at        DATETIME
  updated_at        DATETIME

Database: SQLite
Date functions: strftime('%Y-%m', transaction_date) for year-month grouping
                date(transaction_date) for date-only comparison
                strftime('%Y', transaction_date) for year
"""

_SQL_SYSTEM_PROMPT = f"""You are a SQLite query writer for a personal finance app.

{_SCHEMA}

Rules:
- Write ONE valid SQLite SELECT statement only
- No markdown, no explanation, no code fences — raw SQL only
- Always add ORDER BY and LIMIT 50 unless the question asks for aggregates
- Use LOWER() for case-insensitive text matching
- Use strftime for date grouping
- For "top N", use ORDER BY ... DESC LIMIT N
- Never use DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE
"""

_RETRY_SUFFIX = "\n\nThe previous query failed with this error:\n{error}\n\nWrite a corrected query."

_SYNTHESIS_SYSTEM_PROMPT = """You are a personal finance assistant presenting query results.

Given a user's question, the SQL query that was run, and the raw results,
write a clear, concise natural language answer.

Rules:
- Lead with the direct answer (the number, the list, the comparison)
- Mention currency (INR) when citing amounts
- If results are empty, say so honestly — don't invent data
- Keep it to 2-4 sentences unless a list is genuinely needed
- Do not repeat the SQL back to the user
"""

# ── Safety ─────────────────────────────────────────────────────────────────────

_DANGEROUS_KEYWORDS = {
    "drop", "delete", "insert", "update", "alter",
    "create", "truncate", "replace", "attach", "detach",
}


def _is_safe_sql(sql: str) -> bool:
    """
    Returns True only if the SQL is a read-only SELECT statement.
    Checks both the first keyword and absence of dangerous keywords anywhere.
    """
    normalized = sql.strip().lower()
    if not normalized.startswith("select"):
        return False
    tokens = set(re.findall(r"\b\w+\b", normalized))
    return tokens.isdisjoint(_DANGEROUS_KEYWORDS)


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class SQLAgentResult:
    question: str
    sql: str                              # generated SQL (shown to user)
    rows: List[Dict[str, Any]]            # raw query results
    answer: str                           # LLM-synthesized natural language answer
    retried: bool = False                 # True if a retry was needed
    error: Optional[str] = None          # set if the agent ultimately failed


# ── Agent ──────────────────────────────────────────────────────────────────────

class SQLAgent:
    """
    Two-call agent: generates SQL from a question, executes it,
    then synthesizes a natural language answer from the results.
    """

    def __init__(self, llm: BaseLLMClient, engine: Engine):
        self.llm = llm
        self.engine = engine

    def run(self, question: str) -> SQLAgentResult:
        """
        Full pipeline: question → SQL → execute → answer.
        Returns a SQLAgentResult regardless of success or failure.
        """
        logger.info("sql_agent_start", question=question[:80])

        # ── Step 1: generate SQL ───────────────────────────────────────────────
        sql = self._generate_sql(question)
        logger.info("sql_agent_generated", sql=sql[:200])

        # ── Step 2: safety check ───────────────────────────────────────────────
        if not _is_safe_sql(sql):
            logger.warning("sql_agent_unsafe_query_blocked", sql=sql[:200])
            return SQLAgentResult(
                question=question,
                sql=sql,
                rows=[],
                answer="I can only run read-only queries. The generated SQL was blocked for safety.",
                error="unsafe_sql",
            )

        # ── Step 3: execute (with one retry on error) ─────────────────────────
        rows, exec_error = self._execute(sql)
        retried = False

        if exec_error:
            logger.warning("sql_agent_exec_error_retrying", error=exec_error)
            sql = self._generate_sql(question, prior_error=exec_error)
            retried = True

            if not _is_safe_sql(sql):
                return SQLAgentResult(
                    question=question,
                    sql=sql,
                    rows=[],
                    answer="Retry produced an unsafe query. Please rephrase your question.",
                    retried=True,
                    error="unsafe_sql_on_retry",
                )

            rows, exec_error = self._execute(sql)

        if exec_error:
            logger.error("sql_agent_failed_after_retry", error=exec_error)
            return SQLAgentResult(
                question=question,
                sql=sql,
                rows=[],
                answer=f"I wasn't able to answer that. The query failed: {exec_error}",
                retried=retried,
                error=exec_error,
            )

        # ── Step 4: synthesize answer ──────────────────────────────────────────
        answer = self._synthesize(question, sql, rows)
        logger.info("sql_agent_complete", rows=len(rows), retried=retried)

        return SQLAgentResult(
            question=question,
            sql=sql,
            rows=rows,
            answer=answer,
            retried=retried,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _generate_sql(self, question: str, prior_error: Optional[str] = None) -> str:
        """LLM call 1: natural language → SQL query string."""
        prompt = question
        system = _SQL_SYSTEM_PROMPT
        if prior_error:
            system = _SQL_SYSTEM_PROMPT + _RETRY_SUFFIX.format(error=prior_error)

        raw = self.llm.generate_text(
            prompt=prompt,
            system_prompt=system,
            max_tokens=512,
            temperature=0.0,  # deterministic — SQL generation is not creative
        )
        # Strip markdown fences if the LLM adds them despite instructions
        sql = re.sub(r"```(?:sql)?|```", "", raw).strip()
        return sql

    def _execute(self, sql: str):
        """
        Execute a SELECT query. Returns (rows, error_string).
        rows is a list of dicts; error_string is None on success.
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                keys = list(result.keys())
                rows = [dict(zip(keys, row)) for row in result.fetchall()]
            return rows, None
        except Exception as e:
            return [], str(e)

    def _synthesize(
        self,
        question: str,
        sql: str,
        rows: List[Dict[str, Any]],
    ) -> str:
        """LLM call 2: raw rows → human-readable answer."""
        rows_text = _format_rows_for_prompt(rows)
        prompt = f"""Question: {question}

SQL query run:
{sql}

Results ({len(rows)} rows):
{rows_text}
"""
        return self.llm.generate_text(
            prompt=prompt,
            system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
            max_tokens=512,
            temperature=0.3,
        )


def _format_rows_for_prompt(rows: List[Dict[str, Any]], max_rows: int = 30) -> str:
    """Compact text representation of query results for the synthesis prompt."""
    if not rows:
        return "(no rows returned)"
    shown = rows[:max_rows]
    lines = [", ".join(f"{k}={v}" for k, v in row.items()) for row in shown]
    result = "\n".join(lines)
    if len(rows) > max_rows:
        result += f"\n... and {len(rows) - max_rows} more rows (truncated)"
    return result
