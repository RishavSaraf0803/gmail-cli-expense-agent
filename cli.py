#!/usr/bin/env python
"""
FinCLI - Conversational Gmail Expense Tracker
Command Line Interface
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm
from dateutil import parser as date_parser

from fincli.config import get_settings
from fincli.utils.logger import setup_logging, get_logger
from fincli.storage.database import get_db_manager, init_database
from fincli.clients.gmail_client import get_gmail_client, GmailClientError
from fincli.clients.llm_factory import get_llm_client, LLMClientError
from fincli.extractors.transaction_extractor import (
    get_transaction_extractor,
    TransactionExtractorError
)
from fincli.auth.gmail_auth import test_gmail_connection
from fincli.rag.embedder import OllamaEmbedder, EmbedderError
from fincli.rag.indexer import TransactionIndexer
from fincli.rag.retriever import HybridRetriever
from fincli.tools.filter_tool import FilterTool
from fincli.agents.sql_agent import SQLAgent
from fincli.agents.rag_agent import RAGAgent

# Initialize
app = typer.Typer(
    help="FinCLI: Your Conversational Gmail Expense Tracker",
    add_completion=False
)
console = Console()
settings = get_settings()

# Setup logging
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
    log_file=settings.log_file
)
logger = get_logger(__name__)


def parse_email_date(date_str: str) -> datetime:
    """
    Parse email date string to datetime object.

    Args:
        date_str: Email date string from Gmail headers

    Returns:
        Parsed datetime object, or current time if parsing fails
    """
    if not date_str or date_str == 'Unknown':
        return datetime.now()

    try:
        return date_parser.parse(date_str)
    except Exception as e:
        logger.warning("email_date_parse_failed", date_str=date_str, error=str(e))
        return datetime.now()


def init_app():
    """Initialize application (database, etc.)."""
    try:
        init_database()
        logger.info("application_initialized")
    except Exception as e:
        console.print(f"[red]Failed to initialize application: {e}[/red]")
        logger.error("application_initialization_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def fetch(
    max_emails: int = typer.Option(
        20,
        "--max", "-m",
        help="Maximum number of emails to fetch"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force re-processing of existing emails"
    )
):
    """
    Fetch transaction emails, extract details using LLM, and save to database.
    """
    init_app()

    console.print("[bold cyan]Fetching transaction emails...[/bold cyan]")
    logger.info("fetch_command_started", max_emails=max_emails)

    try:
        # Test Gmail connection
        console.print("Testing Gmail connection...")
        if not test_gmail_connection():
            console.print("[red]Gmail connection failed. Please check your credentials.[/red]")
            raise typer.Exit(code=1)

        # Get clients
        gmail_client = get_gmail_client()
        extractor = get_transaction_extractor()
        db = get_db_manager()

        # Fetch emails
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task(
                "Fetching emails from Gmail...",
                total=None
            )

            emails = gmail_client.fetch_messages(max_results=max_emails)
            progress.update(task, completed=True)

        if not emails:
            console.print("[yellow]No transaction emails found.[/yellow]")
            return

        console.print(f"[green]Found {len(emails)} emails[/green]")

        # Extract and save transactions
        new_count = 0
        skipped_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task(
                "Processing emails...",
                total=len(emails)
            )

            for email in emails:
                try:
                    # Check if already processed
                    if not force and db.get_transaction_by_email_id(email.message_id):
                        skipped_count += 1
                        progress.advance(task)
                        continue

                    # Extract transaction
                    transaction = extractor.extract_from_email(email)

                    if transaction is None:
                        error_count += 1
                        progress.advance(task)
                        continue

                    # Save to database
                    result = db.add_transaction(
                        email_id=email.message_id,
                        amount=transaction.amount,
                        transaction_type=transaction.transaction_type,
                        merchant=transaction.merchant,
                        transaction_date=transaction.transaction_date,
                        currency=transaction.currency,
                        email_subject=email.subject,
                        email_snippet=email.snippet,
                        email_date=parse_email_date(email.date),
                        category=transaction.category,
                        payment_method=transaction.payment_method
                    )

                    if result:
                        new_count += 1

                    progress.advance(task)

                except Exception as e:
                    logger.error(
                        "email_processing_failed",
                        email_id=email.message_id,
                        error=str(e)
                    )
                    error_count += 1
                    progress.advance(task)
                    continue

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  New transactions: [green]{new_count}[/green]")
        console.print(f"  Skipped (duplicates): [yellow]{skipped_count}[/yellow]")
        console.print(f"  Errors: [red]{error_count}[/red]")
        console.print(f"  Total in database: [cyan]{db.count_transactions()}[/cyan]")

        logger.info(
            "fetch_command_completed",
            new=new_count,
            skipped=skipped_count,
            errors=error_count
        )

    except (GmailClientError, TransactionExtractorError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.error("fetch_command_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def summarize():
    """
    Display a summary of your spending.
    """
    init_app()

    console.print("[bold cyan]Spending Summary[/bold cyan]\n")
    logger.info("summarize_command_started")

    try:
        db = get_db_manager()

        total_count = db.count_transactions()
        if total_count == 0:
            console.print("[yellow]No transactions found. Run 'fetch' first.[/yellow]")
            return

        # Calculate totals
        total_spent = db.get_total_by_type('debit')
        total_credited = db.get_total_by_type('credit')
        net = total_credited - total_spent

        # Get top merchants
        top_merchants = db.get_top_merchants(transaction_type='debit', limit=5)

        # Display summary
        table = Table(title="Financial Summary", show_header=False)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Amount", style="magenta")

        table.add_row("Total Spent", f"₹{total_spent:,.2f}")
        table.add_row("Total Credited", f"₹{total_credited:,.2f}")
        table.add_row("Net", f"₹{net:,.2f}")
        table.add_row("Total Transactions", str(total_count))

        console.print(table)

        # Top merchants
        if top_merchants:
            console.print("\n[bold]Top 5 Merchants (by transaction count):[/bold]")
            for i, (merchant, count) in enumerate(top_merchants, 1):
                console.print(f"  {i}. {merchant}: [cyan]{count}[/cyan] transactions")

        logger.info("summarize_command_completed")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("summarize_command_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def index(
    reindex: bool = typer.Option(False, "--reindex", "-r", help="Force re-embed all transactions"),
):
    """
    Build the RAG search index from your transactions.

    Run this after 'fetch' to make new transactions searchable in chat.
    Uses Ollama nomic-embed-text to generate embeddings locally (free).
    """
    init_app()
    logger.info("index_command_started", reindex=reindex)

    try:
        db = get_db_manager()
        embedder = OllamaEmbedder()

        if not embedder.health_check():
            console.print(
                "[red]Ollama embedding model not available.[/red]\n"
                f"[yellow]Run: ollama pull {embedder.model}[/yellow]"
            )
            raise typer.Exit(code=1)

        with db.get_session() as session:
            indexer = TransactionIndexer(session, embedder)

            if reindex:
                console.print("[yellow]Re-indexing all transactions...[/yellow]")
                count = indexer.reindex_all()
            else:
                count = indexer.index_new()

        if count == 0:
            console.print("[green]Index is up to date — nothing new to index.[/green]")
        else:
            console.print(f"[green]Indexed {count} transaction(s).[/green]")

        logger.info("index_command_completed", indexed=count)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("index_command_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def chat():
    """
    Start an interactive Q&A session about your expenses (RAG-powered).

    Each question retrieves the most relevant transactions via semantic search,
    then passes only those as context to the LLM — more accurate, less token waste.

    Run 'index' first to build the search index.
    """
    init_app()

    console.print("[bold cyan]FinCLI Chat[/bold cyan]")
    console.print("Ask me about your expenses. Type 'exit' or 'quit' to end.\n")
    logger.info("chat_command_started")

    try:
        db = get_db_manager()
        llm_client = get_llm_client()

        if db.count_transactions() == 0:
            console.print("[yellow]No transactions found. Run 'fetch' first.[/yellow]")
            return

        embedder = OllamaEmbedder()
        rag_available = embedder.health_check()

        if not rag_available:
            console.print(
                f"[yellow]RAG index unavailable (run: ollama pull {embedder.model}). "
                "Falling back to last-50 context.[/yellow]\n"
            )

        with db.get_session() as session:
            filter_tool = FilterTool(llm_client)

            if rag_available:
                retriever = HybridRetriever(session, embedder, filter_tool)
                rag_agent = RAGAgent(retriever=retriever, llm=llm_client)
            else:
                rag_agent = None

            # Build fallback context once (used only when RAG is unavailable)
            fallback_context = None
            if not rag_available:
                recent = db.get_all_transactions(limit=50)
                fallback_lines = []
                for txn in recent:
                    date_str = txn.transaction_date.strftime("%Y-%m-%d")
                    fallback_lines.append(
                        f"- {txn.transaction_type} of {txn.currency} {txn.amount} "
                        f"for {txn.merchant} on {date_str}."
                    )
                fallback_context = "\n".join(fallback_lines)

            while True:
                question = console.input("[bold green]You >[/bold green] ")

                if question.lower().strip() in ["exit", "quit", "q"]:
                    console.print("[bold cyan]FinCLI >[/bold cyan] Goodbye!")
                    break

                if not question.strip():
                    continue

                try:
                    with console.status("[bold yellow]Thinking...", spinner="dots"):
                        if rag_agent:
                            # RAG agent: self-correcting retrieval + synthesis
                            result = rag_agent.run(question, top_k=8)
                            answer = result.answer
                            rephrased = result.rephrased
                            rephrased_query = result.final_query
                        else:
                            # Fallback: plain LLM with last-50 context
                            prompt = f"""You are FinCLI, a helpful personal finance assistant.
Answer the user's question using ONLY the transaction data below.
If the data doesn't contain enough information, say so honestly.
Be concise. When citing amounts, include the currency and date.

Relevant Transactions:
{fallback_context}

User: {question}
Answer:"""
                            answer = llm_client.generate_text(
                                prompt=prompt,
                                max_tokens=1024,
                                temperature=0.3,
                            )
                            rephrased = False

                    if rephrased:
                        console.print(
                            f"[dim](rephrased: {rephrased_query})[/dim]"
                        )
                    console.print(f"[bold cyan]FinCLI >[/bold cyan] {answer}\n")

                except (LLMClientError, EmbedderError) as e:
                    console.print(f"[red]Error: {e}[/red]\n")
                    logger.error("chat_response_failed", error=str(e))

        logger.info("chat_command_completed")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("chat_command_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question about your expenses"),
):
    """
    Ask a precise question about your expenses using AI-generated SQL.

    Unlike 'chat' (which uses semantic search), 'query' writes and runs
    a real SQL query — perfect for exact totals, counts, and rankings.

    Examples:
      fincli query "how much did I spend in April?"
      fincli query "top 5 merchants by total spend"
      fincli query "total debits grouped by category"
    """
    init_app()
    logger.info("query_command_started", question=question)

    try:
        db = get_db_manager()
        llm_client = get_llm_client()

        if db.count_transactions() == 0:
            console.print("[yellow]No transactions found. Run 'fetch' first.[/yellow]")
            return

        agent = SQLAgent(llm=llm_client, engine=db.engine)

        with console.status("[bold yellow]Writing query...", spinner="dots"):
            result = agent.run(question)

        # ── Show generated SQL ─────────────────────────────────────────────────
        from rich.panel import Panel
        from rich.syntax import Syntax
        retry_note = " [yellow](retried)[/yellow]" if result.retried else ""
        sql_display = Syntax(result.sql, "sql", theme="monokai", word_wrap=True)
        console.print(Panel(sql_display, title=f"[bold]Generated SQL{retry_note}[/bold]", border_style="dim"))

        # ── Show raw results table ─────────────────────────────────────────────
        if result.rows:
            table = Table(title=f"Results ({len(result.rows)} rows)", show_lines=False)
            for col in result.rows[0].keys():
                table.add_column(str(col), style="cyan", no_wrap=True)
            for row in result.rows[:15]:  # cap display at 15 rows
                table.add_row(*[str(v) if v is not None else "—" for v in row.values()])
            if len(result.rows) > 15:
                console.print(f"[dim]  ... and {len(result.rows) - 15} more rows[/dim]")
            console.print(table)
        elif not result.error:
            console.print("[dim]Query returned no rows.[/dim]")

        # ── Show answer ────────────────────────────────────────────────────────
        console.print(f"\n[bold cyan]FinCLI >[/bold cyan] {result.answer}\n")

        logger.info("query_command_completed", rows=len(result.rows), retried=result.retried)

    except (LLMClientError,) as e:
        console.print(f"[red]LLM error: {e}[/red]")
        logger.error("query_command_failed", error=str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("query_command_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def list_transactions(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of transactions to show"),
    transaction_type: str = typer.Option(None, "--type", "-t", help="Filter by type (debit/credit)"),
    merchant: str = typer.Option(None, "--merchant", "-m", help="Filter by merchant name")
):
    """
    List recent transactions.
    """
    init_app()

    try:
        db = get_db_manager()

        # Fetch transactions based on filters
        if merchant:
            transactions = db.get_transactions_by_merchant(merchant, limit=limit)
        elif transaction_type:
            transactions = db.get_transactions_by_type(transaction_type, limit=limit)
        else:
            transactions = db.get_all_transactions(limit=limit)

        if not transactions:
            console.print("[yellow]No transactions found.[/yellow]")
            return

        # Display as table
        table = Table(title=f"Recent Transactions (showing {len(transactions)})")
        table.add_column("Date", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Merchant", style="green")
        table.add_column("Amount", style="yellow", justify="right")

        for txn in transactions:
            date_str = txn.transaction_date.strftime('%Y-%m-%d')
            amount_str = f"{txn.currency} {txn.amount:,.2f}"
            table.add_row(date_str, txn.transaction_type, txn.merchant, amount_str)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error("list_command_failed", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def init():
    """
    Initialize the database and check connections.
    """
    console.print("[bold cyan]Initializing FinCLI...[/bold cyan]\n")

    try:
        # Initialize database
        console.print("Creating database tables...")
        init_database()
        console.print("[green]✓ Database initialized[/green]")

        # Test Gmail connection
        console.print("Testing Gmail connection...")
        if test_gmail_connection():
            console.print("[green]✓ Gmail connection successful[/green]")
        else:
            console.print("[yellow]⚠ Gmail connection failed. You may need to authenticate.[/yellow]")

        # Test LLM connection
        console.print(f"Testing LLM connection ({settings.llm_provider})...")
        try:
            llm_client = get_llm_client()
            if llm_client.health_check():
                console.print(f"[green]✓ LLM connection successful ({settings.llm_provider})[/green]")
            else:
                console.print(f"[yellow]⚠ LLM health check failed[/yellow]")
        except Exception as e:
            console.print(f"[yellow]⚠ LLM connection failed: {e}[/yellow]")

        console.print("\n[bold green]Initialization complete![/bold green]")
        console.print("Run 'fetch' to start importing transactions.")

    except Exception as e:
        console.print(f"[red]Initialization failed: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
