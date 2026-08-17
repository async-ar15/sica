import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # pyright: ignore[reportAttributeAccessIssue]

import asyncio

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Self-Improving Coding Agent CLI")
console = Console()

try:
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
except ImportError as e:
    console.print(f"[bold red]Missing optional dependency:[/bold red] {e}")
    console.print("[yellow]Please ensure you have installed all dependencies: `uv sync`[/yellow]")
    console.print("[yellow]If you are missing docker or chromadb, those are optional but recommended.[/yellow]")
    sys.exit(1)

@app.command()
def run(goal: str, mode: str = "build", max_iterations: int = 10, verbose: bool = False) -> None:
    """Run the autonomous coding agent with a specific goal."""
    load_dotenv()

    display = StatusDisplay()
    try:
        with display.loading_state("Verifying Docker availability..."):
            sandbox = DockerSandbox()
            sandbox.cleanup_orphans()
    except Exception as e:
        display.display_error(f"Docker is unavailable: {e}")
        console.print("[yellow]Please ensure Docker Desktop is running. To run without Docker, set DOCKER_ENABLED=false[/yellow]")
        sys.exit(1)

    with display.loading_state("Loading model configuration..."):
        llm = LLMProvider()

    with display.loading_state("Loading memory from previous sessions..."):
        memory = WorkingMemory()
        session_memory = SessionMemory()
        indexed_memory = IndexedMemory()
        failure_memory = FailureMemory()

    reflection_engine = ReflectionEngine(llm=llm, failure_memory=failure_memory)

    with display.loading_state("Building codebase structure map..."):
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
            import yaml
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
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] config/default.yaml not found.")
    except yaml.YAMLError as e:  # pyright: ignore[reportPossiblyUnboundVariable]
        console.print(f"[bold red]Config Syntax Error:[/bold red] The config file is not valid YAML.\nDetails: {e}")
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {e}")

@app.command()
def version() -> None:
    """Display the agent version."""
    console.print("Self-Improving Coding Agent v0.1.0")

@app.command()
def replay(task_id: str) -> None:
    """Interactively step through a task's trajectory."""
    from agent.core.trajectory import TrajectoryLogger
    logger = TrajectoryLogger(task_id=task_id)
    logger.replay()

@app.command()
def export(task_id: str, format: str = "markdown") -> None:
    """Export a task's trajectory to a document."""
    from agent.core.trajectory import TrajectoryLogger
    logger = TrajectoryLogger(task_id=task_id)
    out = logger.export(format=format)
    console.print("[bold green]Exported to markdown successfully.[/bold green]")

@app.command()
def dream() -> None:
    """Run memory maintenance and pruning."""
    import asyncio
    from agent.memory.dream import DreamEngine
    from agent.memory.session import SessionMemory
    from agent.memory.indexed import IndexedMemory
    from agent.memory.failure import FailureMemory
    from providers.embeddings import EmbeddingProvider
    from providers.llm import LLMProvider

    engine = DreamEngine(
        session=SessionMemory(),
        indexed=IndexedMemory(),
        failure=FailureMemory(),
        embeddings=EmbeddingProvider(),
        llm=LLMProvider()
    )
    asyncio.run(engine.run("."))
    console.print("[bold green]Memory maintenance complete.[/bold green]")

@app.command()
def distill() -> None:
    """Extract skills from successful task trajectories."""
    import asyncio
    from agent.memory.distill import DistillEngine
    from agent.memory.failure import FailureMemory
    from providers.embeddings import EmbeddingProvider
    from providers.llm import LLMProvider

    engine = DistillEngine(
        trajectory_dir="logs/trajectories",
        embeddings=EmbeddingProvider(),
        llm=LLMProvider(),
        failure_memory=FailureMemory()
    )
    asyncio.run(engine.run())
    console.print("[bold green]Skill extraction complete.[/bold green]")

@app.command("eval")
def evaluate(tasks_dir: str = "eval/tasks") -> None:
    """Run the evaluation harness on tasks."""
    import asyncio

    from agent.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
    from agent.core.harness import AgentHarness
    from agent.core.state_machine import StateMachine
    from agent.core.trajectory import TrajectoryLogger
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
    from eval.harness import EvaluationHarness
    from providers.llm import LLMProvider
    from ui.display import StatusDisplay

    # We create a dummy harness just to pass into EvaluationHarness
    # Actual evaluation requires full isolation per task.
    llm = LLMProvider()
    sandbox = DockerSandbox()
    memory = WorkingMemory()
    fmemory = FailureMemory()
    re = ReflectionEngine(llm, fmemory)
    rm = RepoMap(".")
    fl = FaultLocalizer(llm, rm)
    sa = StaticAnalyzer(sandbox)
    tr = ToolRegistry(sandbox, memory, PermissionGate(AgentMode.BUILD))

    agent = AgentHarness(
        llm=llm, sandbox=sandbox, tools=tr, fsm=StateMachine(),
        circuit_breaker=CircuitBreaker(CircuitBreakerConfig()),
        memory=memory, session_memory=SessionMemory(),
        indexed_memory=IndexedMemory(), failure_memory=fmemory,
        reflection_engine=re, repo_map=rm, fault_localizer=fl,
        static_analyzer=sa, display=StatusDisplay(),
        trajectory=TrajectoryLogger("eval")
    )

    harness = EvaluationHarness(agent)
    console.print(f"[bold cyan]Running evaluation on tasks from {tasks_dir}[/bold cyan]")
    report = asyncio.run(harness.run())
    console.print(f"[bold green]Eval complete! Solve rate: {report.solve_rate}%[/bold green]")

@app.command()
def search(query: str) -> None:
    """Search Indexed Memory (FTS5)."""
    from agent.memory.indexed import IndexedMemory
    mem = IndexedMemory()
    results = mem.search(query)
    for r in results:
        console.print(f"Fact: {r.content}")

if __name__ == "__main__":
    app()
