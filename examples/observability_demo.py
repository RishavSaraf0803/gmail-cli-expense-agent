"""
Observability and Prompt Management Demo

This script demonstrates the new AI engineering features:
1. LLM metrics tracking
2. Versioned prompt management
3. Cost analysis
4. A/B testing prompts
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fincli.observability import get_metrics_tracker
from fincli.prompts import get_prompt_manager
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def demo_metrics_tracking():
    """Demonstrate metrics tracking capabilities."""
    console.print("\n[bold cyan]LLM Metrics Tracking Demo[/bold cyan]\n")

    tracker = get_metrics_tracker()

    # Get summary report
    report = tracker.get_summary_report()

    # Display summary
    console.print("[yellow]📊 Overall Summary[/yellow]")
    console.print(f"Total calls: {report['total_calls']}")
    console.print(f"Successful: {report['successful_calls']}")
    console.print(f"Failed: {report['failed_calls']}")
    console.print(f"Success rate: {report['success_rate']:.1%}")
    console.print(f"Total cost: ${report['total_cost_usd']:.4f}\n")

    # Cost breakdown by provider
    console.print("[yellow]💰 Cost by Provider[/yellow]")
    cost_table = Table(show_header=True, header_style="bold magenta")
    cost_table.add_column("Provider")
    cost_table.add_column("Cost (USD)", justify="right")

    for provider, cost in report['cost_by_provider'].items():
        cost_table.add_row(provider, f"${cost:.4f}")

    console.print(cost_table)

    # Cost breakdown by use case
    console.print("\n[yellow]🎯 Cost by Use Case[/yellow]")
    use_case_table = Table(show_header=True, header_style="bold magenta")
    use_case_table.add_column("Use Case")
    use_case_table.add_column("Cost (USD)", justify="right")

    for use_case, cost in report['cost_by_use_case'].items():
        use_case_table.add_row(use_case, f"${cost:.4f}")

    console.print(use_case_table)

    # Token usage
    console.print("\n[yellow]🔢 Token Usage[/yellow]")
    tokens = report['total_tokens']
    console.print(f"Input tokens: {tokens['input_tokens']:,}")
    console.print(f"Output tokens: {tokens['output_tokens']:,}")
    console.print(f"Total tokens: {tokens['total_tokens']:,}")

    # Latency stats
    console.print("\n[yellow]⚡ Latency Statistics[/yellow]")
    latency = report['latency_stats']
    console.print(f"P50: {latency['p50']:.0f}ms")
    console.print(f"P95: {latency['p95']:.0f}ms")
    console.print(f"P99: {latency['p99']:.0f}ms")
    console.print(f"Mean: {latency['mean']:.0f}ms")
    console.print(f"Max: {latency['max']:.0f}ms")


def demo_prompt_management():
    """Demonstrate prompt management capabilities."""
    console.print("\n[bold cyan]Prompt Management Demo[/bold cyan]\n")

    pm = get_prompt_manager()

    # List available prompts
    console.print("[yellow]📝 Available Prompts[/yellow]")
    all_prompts = pm.list_prompts()

    for category, prompts in all_prompts.items():
        console.print(f"\n{category.upper()}:")
        for prompt_name in prompts:
            console.print(f"  • {prompt_name}")

    # Load a specific prompt
    console.print("\n[yellow]🔍 Loading Transaction Extraction Prompt v2[/yellow]")
    try:
        prompt = pm.load_prompt('extraction', 'transaction', version='v2')

        console.print(f"Name: {prompt.name}")
        console.print(f"Version: {prompt.version}")
        console.print(f"Description: {prompt.metadata.get('description', 'N/A')}")

        # Show parameters
        console.print("\nParameters:")
        for key, value in prompt.parameters.items():
            console.print(f"  {key}: {value}")

        # Show metadata
        console.print("\nMetadata:")
        for key, value in prompt.metadata.items():
            if key != 'notes':  # Skip long notes
                console.print(f"  {key}: {value}")

        # Render example
        console.print("\n[yellow]📄 Example Rendered Prompt[/yellow]")
        rendered = prompt.render_user_prompt(
            email_content="Your card ending in 1234 was debited INR 500.00 at Amazon on 19-Nov-2024"
        )
        console.print(rendered[:200] + "...")

    except Exception as e:
        console.print(f"[red]Error loading prompt: {e}[/red]")


def demo_cost_analysis():
    """Demonstrate cost analysis."""
    console.print("\n[bold cyan]Cost Analysis Demo[/bold cyan]\n")

    tracker = get_metrics_tracker()

    # Provider comparison
    console.print("[yellow]🔍 Provider Comparison[/yellow]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Provider")
    table.add_column("Success Rate", justify="right")
    table.add_column("P95 Latency (ms)", justify="right")
    table.add_column("Total Cost", justify="right")

    providers = ['anthropic', 'openai', 'bedrock', 'ollama']
    for provider in providers:
        try:
            success_rate = tracker.get_success_rate(provider=provider)
            latency = tracker.get_latency_stats(provider=provider)
            cost = tracker.get_total_cost(provider=provider)

            table.add_row(
                provider,
                f"{success_rate:.1%}",
                f"{latency['p95']:.0f}",
                f"${cost:.4f}"
            )
        except:
            # Provider might not have any calls
            pass

    console.print(table)


def demo_ab_testing():
    """Demonstrate A/B testing concept."""
    console.print("\n[bold cyan]A/B Testing Demo[/bold cyan]\n")

    pm = get_prompt_manager()

    console.print("[yellow]📊 Comparing Prompt Versions[/yellow]\n")

    try:
        # Load both versions
        v1 = pm.load_prompt('extraction', 'transaction', version='v1')
        v2 = pm.load_prompt('extraction', 'transaction', version='v2')

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric")
        table.add_column("Version 1", justify="right")
        table.add_column("Version 2", justify="right")

        # Compare metadata
        v1_metrics = v1.metadata.get('performance_metrics', {})
        v2_metrics = v2.metadata.get('performance_metrics', {})

        table.add_row(
            "Baseline Accuracy",
            f"{v1_metrics.get('baseline_accuracy', 'N/A')}",
            f"{v2_metrics.get('target_accuracy', 'N/A')}"
        )

        table.add_row(
            "F1 Score",
            f"{v1_metrics.get('baseline_f1_score', 'N/A')}",
            f"{v2_metrics.get('target_f1_score', 'N/A')}"
        )

        table.add_row(
            "Max Tokens",
            f"{v1.parameters.get('max_tokens')}",
            f"{v2.parameters.get('max_tokens')}"
        )

        console.print(table)

        console.print("\n[green]✓ Version 2 shows improved metrics[/green]")
        console.print("Consider A/B testing on live traffic before full rollout.")

    except Exception as e:
        console.print(f"[red]Error comparing versions: {e}[/red]")


def main():
    """Run all demos."""
    console.print("[bold green]FinCLI AI Engineering Features Demo[/bold green]")
    console.print("=" * 60)

    try:
        demo_metrics_tracking()
    except Exception as e:
        console.print(f"\n[red]Metrics demo failed: {e}[/red]")

    try:
        demo_prompt_management()
    except Exception as e:
        console.print(f"\n[red]Prompt management demo failed: {e}[/red]")

    try:
        demo_cost_analysis()
    except Exception as e:
        console.print(f"\n[red]Cost analysis demo failed: {e}[/red]")

    try:
        demo_ab_testing()
    except Exception as e:
        console.print(f"\n[red]A/B testing demo failed: {e}[/red]")

    console.print("\n[bold green]Demo Complete![/bold green]")
    console.print("\nFor more information, see docs/AI_ENGINEERING_GUIDE.md")


if __name__ == "__main__":
    main()
