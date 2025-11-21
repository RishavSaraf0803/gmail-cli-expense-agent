"""
LLM Response Caching Demo

This script demonstrates the cost optimization benefits of response caching:
1. Cache hit/miss behavior
2. Cost savings calculation
3. Performance improvements
4. Cache statistics
"""
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fincli.cache import get_cache_manager, LLMCache
from fincli.clients.anthropic_client import get_anthropic_client
from fincli.observability import get_metrics_tracker
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def demo_cache_basics():
    """Demonstrate basic cache hit/miss behavior."""
    console.print("\n[bold cyan]1. Cache Basics: Hit vs Miss[/bold cyan]\n")

    cache_manager = get_cache_manager()
    cache_manager.clear()  # Start fresh

    # Simulate LLM responses
    test_prompts = [
        "Extract transaction from: Spent ₹500 at Amazon",
        "Extract transaction from: Spent ₹500 at Amazon",  # Duplicate
        "Extract transaction from: Spent ₹1000 at Flipkart",
        "Extract transaction from: Spent ₹500 at Amazon",  # Duplicate again
    ]

    console.print("[yellow]Processing prompts...[/yellow]\n")

    for i, prompt in enumerate(test_prompts, 1):
        # Check cache
        cached = cache_manager.get(
            prompt=prompt,
            model="claude-3-5-sonnet",
            provider="anthropic",
            temperature=0.0,
            max_tokens=500
        )

        if cached:
            console.print(f"[green]✓[/green] Prompt {i}: CACHE HIT")
        else:
            console.print(f"[red]✗[/red] Prompt {i}: CACHE MISS - Calling API")

            # Simulate API call
            time.sleep(0.1)
            response = f'{{"amount": 500, "merchant": "Amazon"}}'

            # Store in cache
            cache_manager.set(
                prompt=prompt,
                response=response,
                model="claude-3-5-sonnet",
                provider="anthropic",
                input_tokens=850,
                output_tokens=120,
                temperature=0.0,
                max_tokens=500
            )

    # Show stats
    stats = cache_manager.get_stats()
    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Hits: {stats.total_hits}")
    console.print(f"  Misses: {stats.total_misses}")
    console.print(f"  Hit Rate: {stats.hit_rate:.1%}")


def demo_cost_savings():
    """Demonstrate cost savings from caching."""
    console.print("\n[bold cyan]2. Cost Savings Analysis[/bold cyan]\n")

    cache_manager = get_cache_manager()
    cache_manager.clear()

    # Simulate batch processing with duplicates
    num_emails = 100
    num_unique = 30  # 70% duplicates!

    console.print(f"[yellow]Simulating {num_emails} emails ({num_unique} unique)[/yellow]\n")

    # Generate emails with duplicates
    emails = []
    for i in range(num_unique):
        emails.append(f"Email {i}: Spent ₹{(i+1)*100} at Merchant{i}")

    # Add duplicates
    import random
    while len(emails) < num_emails:
        emails.append(random.choice(emails[:num_unique]))

    random.shuffle(emails)

    # Process with cache
    api_calls = 0
    cache_hits = 0

    with console.status("[bold green]Processing emails..."):
        for email in emails:
            cached = cache_manager.get(
                prompt=email,
                model="claude-3-5-sonnet",
                provider="anthropic",
                temperature=0.0,
                max_tokens=500
            )

            if not cached:
                # Simulate API call
                api_calls += 1
                time.sleep(0.01)  # Simulate latency

                cache_manager.set(
                    prompt=email,
                    response='{"amount": 500}',
                    model="claude-3-5-sonnet",
                    provider="anthropic",
                    input_tokens=850,
                    output_tokens=120,
                    temperature=0.0,
                    max_tokens=500
                )
            else:
                cache_hits += 1

    # Calculate costs
    cost_per_call = 0.003 * (850/1000) + 0.015 * (120/1000)  # Anthropic pricing
    cost_without_cache = num_emails * cost_per_call
    cost_with_cache = api_calls * cost_per_call
    savings = cost_without_cache - cost_with_cache
    savings_percent = (savings / cost_without_cache) * 100

    # Display results
    table = Table(title="Cost Analysis", show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Without Cache", justify="right")
    table.add_column("With Cache", justify="right")
    table.add_column("Savings", justify="right", style="green")

    table.add_row("Total Requests", f"{num_emails}", f"{num_emails}", "-")
    table.add_row("API Calls", f"{num_emails}", f"{api_calls}", f"{num_emails - api_calls}")
    table.add_row("Cache Hits", "0", f"{cache_hits}", f"{cache_hits}")
    table.add_row("Cost (USD)", f"${cost_without_cache:.4f}", f"${cost_with_cache:.4f}", f"${savings:.4f}")
    table.add_row("Hit Rate", "0%", f"{(cache_hits/num_emails)*100:.1f}%", "-")

    console.print(table)
    console.print(f"\n[bold green]💰 You saved {savings_percent:.1f}% on costs![/bold green]")


def demo_cache_statistics():
    """Demonstrate cache statistics and monitoring."""
    console.print("\n[bold cyan]3. Cache Statistics & Monitoring[/bold cyan]\n")

    cache_manager = get_cache_manager()
    stats = cache_manager.get_stats()

    # Display comprehensive stats
    console.print("[yellow]📊 Current Cache Statistics[/yellow]\n")

    stats_table = Table(show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", justify="right")

    stats_table.add_row("Total Hits", f"{stats.total_hits:,}")
    stats_table.add_row("Total Misses", f"{stats.total_misses:,}")
    stats_table.add_row("Hit Rate", f"{stats.hit_rate:.1%}")
    stats_table.add_row("Cache Entries", f"{stats.total_entries:,}")
    stats_table.add_row("Evictions", f"{stats.total_evictions:,}")
    stats_table.add_row("Tokens Saved", f"{stats.tokens_saved:,}")
    stats_table.add_row("Cost Saved", f"${stats.cost_saved_usd:.4f}")

    console.print(stats_table)

    # Recommendations
    console.print("\n[yellow]💡 Recommendations[/yellow]\n")

    if stats.hit_rate < 0.3:
        console.print("[red]• Hit rate is low (<30%). Consider:")
        console.print("  - Increasing cache_max_entries")
        console.print("  - Increasing cache_ttl_seconds")
        console.print("  - Normalizing prompt parameters")
    elif stats.hit_rate > 0.7:
        console.print("[green]• Excellent hit rate (>70%)!")
        console.print("  - Current cache settings are optimal")
    else:
        console.print("[yellow]• Good hit rate (30-70%)")
        console.print("  - Cache is working well")


def demo_cache_key_sensitivity():
    """Demonstrate how cache keys work with different parameters."""
    console.print("\n[bold cyan]4. Cache Key Sensitivity[/bold cyan]\n")

    cache_manager = get_cache_manager()
    cache_manager.clear()

    prompt = "Extract transaction from email"

    console.print("[yellow]Testing cache key generation...[/yellow]\n")

    # Same parameters = cache hit
    cache_manager.set(
        prompt=prompt,
        response="response1",
        model="claude",
        provider="anthropic",
        input_tokens=100,
        output_tokens=50,
        temperature=0.0,
        max_tokens=500
    )

    cached = cache_manager.get(
        prompt=prompt,
        model="claude",
        provider="anthropic",
        temperature=0.0,
        max_tokens=500
    )
    console.print(f"[green]✓[/green] Same parameters: {['MISS', 'HIT'][bool(cached)]}")

    # Different temperature = cache miss
    cached = cache_manager.get(
        prompt=prompt,
        model="claude",
        provider="anthropic",
        temperature=0.7,  # Different!
        max_tokens=500
    )
    console.print(f"[red]✗[/red] Different temperature: {['MISS', 'HIT'][bool(cached)]}")

    # Different max_tokens = cache miss
    cached = cache_manager.get(
        prompt=prompt,
        model="claude",
        provider="anthropic",
        temperature=0.0,
        max_tokens=1000  # Different!
    )
    console.print(f"[red]✗[/red] Different max_tokens: {['MISS', 'HIT'][bool(cached)]}")

    # Different prompt = cache miss
    cached = cache_manager.get(
        prompt=prompt + " ",  # Trailing space!
        model="claude",
        provider="anthropic",
        temperature=0.0,
        max_tokens=500
    )
    console.print(f"[red]✗[/red] Different prompt (whitespace): {['MISS', 'HIT'][bool(cached)]}")

    console.print("\n[bold]Key Takeaway:[/bold]")
    console.print("Cache keys are sensitive to ALL parameters.")
    console.print("Use consistent parameters for better hit rates!")


def demo_integration_with_observability():
    """Show how cache integrates with observability."""
    console.print("\n[bold cyan]5. Integration with Observability[/bold cyan]\n")

    from fincli.observability import get_metrics_tracker

    tracker = get_metrics_tracker()
    cache_manager = get_cache_manager()

    console.print("[yellow]Cache statistics are automatically included in observability reports![/yellow]\n")

    report = tracker.get_summary_report(include_cache_stats=True)

    if report.get('cache_stats'):
        cache_stats = report['cache_stats']

        console.print("[green]Cache Metrics in Report:[/green]")
        console.print(f"  Hit Rate: {cache_stats.get('hit_rate', 0):.1%}")
        console.print(f"  Total Entries: {cache_stats.get('total_entries', 0)}")
        console.print(f"  Cost Saved: ${cache_stats.get('cost_saved_usd', 0):.4f}")
    else:
        console.print("[yellow]No cache statistics available yet.[/yellow]")

    console.print("\n[bold]Use this for:[/bold]")
    console.print("  • Monitoring cache performance over time")
    console.print("  • Tracking cost savings")
    console.print("  • Optimizing cache configuration")


def main():
    """Run all cache demos."""
    console.print("[bold green]FinCLI Response Caching Demo[/bold green]")
    console.print("=" * 60)

    try:
        demo_cache_basics()
    except Exception as e:
        console.print(f"[red]Cache basics demo failed: {e}[/red]")

    try:
        demo_cost_savings()
    except Exception as e:
        console.print(f"[red]Cost savings demo failed: {e}[/red]")

    try:
        demo_cache_statistics()
    except Exception as e:
        console.print(f"[red]Statistics demo failed: {e}[/red]")

    try:
        demo_cache_key_sensitivity()
    except Exception as e:
        console.print(f"[red]Cache key demo failed: {e}[/red]")

    try:
        demo_integration_with_observability()
    except Exception as e:
        console.print(f"[red]Observability integration demo failed: {e}[/red]")

    console.print("\n[bold green]Demo Complete![/bold green]")
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("  1. Check docs/CACHING_GUIDE.md for full documentation")
    console.print("  2. Configure caching in .env file")
    console.print("  3. Monitor cache hit rates in production")
    console.print("  4. Optimize TTL and max_entries based on metrics")


if __name__ == "__main__":
    main()
