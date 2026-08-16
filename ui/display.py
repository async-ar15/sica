# Stub for TaskResult to avoid circular imports / missing files before Phase 1.9
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.core.state_machine import AgentState
from agent.memory.working import IterationSnapshot


class TaskResult(BaseModel):
    success: bool
    task_id: str = ""
    goal: str = ""
    iterations: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    files_created: list[str] = []
    files_modified: list[str] = []
    reason: str = ""
    summary: str = ""

class StatusDisplay:
    def __init__(self) -> None:
        self.console = Console()

    def update(self, state: AgentState, iteration: int, max_iterations: int, tokens: int, cost: float, message: str) -> None:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("State")
        table.add_column("Iteration")
        table.add_column("Tokens")
        table.add_column("Cost")
        table.add_column("Message")

        color = "white"
        if state == AgentState.COMPLETED:
            color = "green"
        elif state == AgentState.FAILED:
            color = "red"
        elif state in (AgentState.CODING, AgentState.TESTING):
            color = "yellow"
        elif state == AgentState.PLANNING:
            color = "blue"

        table.add_row(
            f"[{color}]{state.value}[/{color}]",
            f"{iteration}/{max_iterations}",
            str(tokens),
            f"${cost:.4f}",
            message
        )
        self.console.print(table)

    def display_iteration(self, snapshot: IterationSnapshot) -> None:
        self.console.print(f"[bold cyan]Iteration {snapshot.iteration} Summary:[/bold cyan]")
        self.console.print(f"Tokens Used: {snapshot.tokens_used}")
        self.console.print(f"Duration: {snapshot.duration_ms}ms")
        if snapshot.errors:
            self.console.print("[bold red]Errors:[/bold red]")
            for err in snapshot.errors:
                self.console.print(f" - {err.error_type}: {err.core_message}")

    def display_result(self, result: TaskResult) -> None:
        title = "[bold green]✅ SUCCESS[/bold green]" if result.success else "[bold red]❌ FAILED[/bold red]"

        content = (
            f"Iterations: {result.iterations}\\n"
            f"Tokens: {result.total_tokens}\\n"
            f"Cost: ${result.total_cost_usd:.4f}\\n"
            f"Files Created: {len(result.files_created)}\\n"
            f"Files Modified: {len(result.files_modified)}\\n"
            f"Summary: {result.summary}\\n"
            f"Reason: {result.reason}"
        )
        self.console.print(Panel(content, title=title))

    def display_error(self, error: str) -> None:
        self.console.print(Panel(error, title="[bold red]Error[/bold red]", border_style="red"))
