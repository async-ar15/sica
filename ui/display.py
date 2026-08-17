# Stub for TaskResult to avoid circular imports / missing files before Phase 1.9
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

from agent.core.state_machine import AgentState
from agent.memory.working import IterationSnapshot

# OpenCode Design System Theme
opencode_theme = Theme({
    "success": "#30d158",
    "danger": "#ff3b30",
    "warning": "#ff9f0a",
    "info": "#007aff",
    "mute": "#9a9898",
    "border": "#646262",
    "primary": "#fdfcfc",
    "primary_bold": "bold #fdfcfc",
})

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
        self.console = Console(theme=opencode_theme)

    def update(self, state: AgentState, iteration: int, max_iterations: int, tokens: int, cost: float, message: str) -> None:
        table = Table(show_header=True, header_style="primary_bold", border_style="border")
        table.add_column("State")
        table.add_column("Iteration")
        table.add_column("Tokens")
        table.add_column("Cost")
        table.add_column("Message")

        color = "primary"
        if state == AgentState.COMPLETED:
            color = "success"
        elif state == AgentState.FAILED:
            color = "danger"
        elif state in (AgentState.CODING, AgentState.TESTING):
            color = "warning"
        elif state == AgentState.PLANNING:
            color = "info"

        table.add_row(
            f"[{color}]{state.value}[/{color}]",
            f"[mute]{iteration}/{max_iterations}[/mute]",
            f"[mute]{tokens}[/mute]",
            f"[mute]${cost:.4f}[/mute]",
            f"[primary]{message}[/primary]"
        )
        self.console.print(table)

    def display_iteration(self, snapshot: IterationSnapshot) -> None:
        self.console.print(f"[bold info]Iteration {snapshot.iteration} Summary:[/bold info]")
        self.console.print(f"[mute]Tokens Used:[/mute] [primary]{snapshot.tokens_used}[/primary]")
        self.console.print(f"[mute]Duration:[/mute] [primary]{snapshot.duration_ms}ms[/primary]")
        if snapshot.errors:
            self.console.print("[bold danger]Errors:[/bold danger]")
            for err in snapshot.errors:
                self.console.print(f" [border]-[/border] [danger]{err.error_type}:[/danger] [primary]{err.core_message}[/primary]")

    def display_result(self, result: TaskResult) -> None:
        if result.success:
            title = "[bold success][+] SUCCESS[/bold success]"
            border = "success"
        else:
            title = "[bold danger][-] FAILED[/bold danger]"
            border = "danger"

        content = (
            f"[mute]Iterations:[/mute] [primary]{result.iterations}[/primary]\\n"
            f"[mute]Tokens:[/mute] [primary]{result.total_tokens}[/primary]\\n"
            f"[mute]Cost:[/mute] [primary]${result.total_cost_usd:.4f}[/primary]\\n"
            f"[mute]Files Created:[/mute] [primary]{len(result.files_created)}[/primary]\\n"
            f"[mute]Files Modified:[/mute] [primary]{len(result.files_modified)}[/primary]\\n"
            f"[mute]Summary:[/mute] [primary]{result.summary}[/primary]\\n"
            f"[mute]Reason:[/mute] [primary]{result.reason}[/primary]"
        )
        self.console.print(Panel(content, title=title, border_style=border))

    def display_error(self, error: str) -> None:
        self.console.print(Panel(f"[primary]{error}[/primary]", title="[bold danger][x] Error[/bold danger]", border_style="danger"))

    def display_message(self, message: str) -> None:
        self.console.print(f"[bold info]{message}[/bold info]")

    import contextlib
    @contextlib.contextmanager
    def loading_state(self, message: str):
        from rich.console import Console
        # We use a separate local console for the status to not mess with the main one
        c = Console()
        with c.status(f"[bold info]{message}[/bold info]", spinner="dots"):
            yield
