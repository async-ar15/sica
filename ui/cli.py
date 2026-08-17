import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from agent.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from agent.core.harness import AgentHarness
from agent.core.state_machine import StateMachine
from agent.memory.failure import FailureMemory
from agent.memory.indexed import IndexedMemory
from agent.memory.session import SessionMemory
from agent.memory.working import WorkingMemory
from agent.reflection.engine import ReflectionEngine
from agent.safety.permissions import PermissionGate
from agent.safety.static_analysis import StaticAnalyzer
from agent.tools.aci import AgentMode, ToolRegistry
from agent.tools.fault_localizer import FaultLocalizer
from agent.tools.repo_map import RepoMap
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
    session_memory = SessionMemory()
    indexed_memory = IndexedMemory()
    failure_memory = FailureMemory()
    reflection_engine = ReflectionEngine(llm=llm, failure_memory=failure_memory)
    repo_map = RepoMap(".")
    fault_localizer = FaultLocalizer(llm=llm, repo_map=repo_map)
    static_analyzer = StaticAnalyzer(sandbox=sandbox)
    try:
        agent_mode = AgentMode(mode.lower())
    except ValueError:
        console.print(f"[bold yellow]Warning:[/bold yellow] Invalid mode '{mode}', defaulting to 'plan'")
        agent_mode = AgentMode.PLAN

    permission_gate = PermissionGate(default_mode=agent_mode)
    tools = ToolRegistry(sandbox=sandbox, working_memory=memory, permission_gate=permission_gate)
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
        session_memory=session_memory,
        indexed_memory=indexed_memory,
        failure_memory=failure_memory,
        reflection_engine=reflection_engine,
        repo_map=repo_map,
        fault_localizer=fault_localizer,
        static_analyzer=static_analyzer,
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
