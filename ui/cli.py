import asyncio
import sys

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from agent.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from agent.core.harness import AgentHarness
from agent.core.state_machine import StateMachine
from agent.memory.working import WorkingMemory
from agent.tools.aci import ToolRegistry
from agent.tools.sandbox import DockerSandbox
from providers.llm import LLMProvider
from ui.display import StatusDisplay

app = typer.Typer(help="Self-Improving Coding Agent CLI")
console = Console()

@app.command()
def run(goal: str, mode: str = "build", max_iterations: int = 10, verbose: bool = False) -> None:
    """Run the autonomous coding agent with a specific goal."""
    load_dotenv()

    display = StatusDisplay()
    try:
        sandbox = DockerSandbox()
        sandbox.cleanup_orphans()
    except Exception as e:
        display.display_error(f"Failed to initialize Sandbox: {e}")
        return

    llm = LLMProvider()
    memory = WorkingMemory()
    tools = ToolRegistry(sandbox=sandbox, working_memory=memory)
    fsm = StateMachine()
    circuit_breaker = CircuitBreaker(CircuitBreakerConfig(max_iterations=max_iterations))

    import time

    from agent.core.trajectory import TrajectoryLogger

    task_id = f"task_{int(time.time())}"
    trajectory = TrajectoryLogger(task_id=task_id)

    harness = AgentHarness(
        llm=llm,
        sandbox=sandbox,
        tools=tools,
        fsm=fsm,
        circuit_breaker=circuit_breaker,
        memory=memory,
        display=display,
        trajectory=trajectory
    )

    console.print(f"[bold cyan]🎯 Goal:[/bold cyan] {goal} [bold]({mode} mode)[/bold]")

    try:
        result = asyncio.run(harness.run(goal))
        display.display_result(result)
    except KeyboardInterrupt:
        console.print("[bold yellow]Interrupted. Cleaning up...[/bold yellow]")
        sandbox.cleanup_orphans()
        sys.exit(130)
    except Exception as e:
        display.display_error(f"Unexpected error: {e}")

@app.command()
def config() -> None:
    """Display the current agent configuration."""
    try:
        with open("config/default.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        table = Table(title="Agent Configuration")
        table.add_column("Category", style="cyan")
        table.add_column("Key", style="magenta")
        table.add_column("Value", style="green")

        for category, items in cfg.items():
            if isinstance(items, dict):
                for k, v in items.items():
                    table.add_row(category, k, str(v))
            else:
                table.add_row("root", category, str(items))

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {e}")

@app.command()
def version() -> None:
    """Display the agent version."""
    console.print("Self-Improving Coding Agent v0.1.0")

if __name__ == "__main__":
    app()
