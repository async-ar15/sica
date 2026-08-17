# Phase 3 Execution Plan — Polish, Deployment & Edge Cases

---

## 1 — AGENT INSTRUCTIONS

1. **Read this entire file before writing a single line of code.** Do not start coding until you have read every section, every phase, every acceptance criterion.
2. **Never change the tech stack without flagging it as a blocker.** The stack in Section 2 is locked. If a dependency is unavailable, broken, or incompatible — stop, log a blocker in `tracker.md`, and ask for human verification.
3. **Always run the project after each phase before marking it complete.** Every phase has Manual Test Steps. Execute them. If they fail, the phase is NOT done.
4. **Never leave a phase half-done across sessions.** Finish the current phase or roll back to the last working state. Do not commit partial work.
5. **Always write types before implementation.** Define Pydantic models, dataclasses, and type aliases FIRST. Then implement logic against them. Never invent types ad hoc.
6. **Strictly follow the design guidelines in Sections 4 and 5.** These are non-negotiable constraints derived from the architecture.
7. **If something is unclear, pause and ask for human verification.** Do not guess at architectural decisions. Do not silently deviate.
8. **ALWAYS log progress, blockers, and architectural deviations in `tracker.md` at the end of every session.** Update the Phase Status Tracker table, the Blockers Log table, and the Deviations/Decisions Log. `tracker.md` is the ONLY file you modify dynamically for project management.
9. **Run `ruff check agent/` and `mypy agent/ --strict` after every phase.** Zero errors required before marking a phase DONE.
10. **Commit after each completed phase** with the message format: `feat(phase-3.N): <one-line summary>`.
11. **Phases 1 and 2 must be fully complete before starting Phase 3.** All Phase 1 and Phase 2 acceptance criteria must pass. If any component is broken, fix it first.
12. **Preserve ALL existing tests.** Every Phase 1 and Phase 2 test must continue to pass after Phase 3 changes. Run `uv run pytest tests/ -v` after every phase.
13. **Phase 3 is the polish layer.** Every component built here should elevate the system from "working prototype" to "portfolio-ready, production-grade agent."

---

## 2 — PROJECT SNAPSHOT

**What:** A production-grade, autonomous, self-improving coding agent in Python that takes a goal, decomposes it into subtasks, writes code in a sandboxed Docker environment, runs tests, and iterates through a Plan → Code → Analyze → Test → Reflect loop until code is functional or a circuit breaker stops it.

**Stack:** Python 3.11+ · `uv` package manager · `pydantic` v2 · `litellm` · `docker` SDK · `rich` + `typer` CLI · `tenacity` · `asyncio` · `tree-sitter` + `tree-sitter-languages` · SQLite FTS5 · ChromaDB · `sentence-transformers` · `gitpython` · `ruff` + `mypy` + `bandit` · `tiktoken`

**Deployment target:** Local CLI tool. No cloud deployment. User runs `uv run agent run "goal"` from their terminal.

**Phase 3 Goal:** Implement the multi-agent pipeline (Architect/Worker/Judge), self-improvement algorithms (`/dream`, `/distill`), multi-candidate fix search, context compaction, cost/token budget system, MCP support, evaluation harness, git integration, error boundaries, complete README, and full E2E test suite — making the agent a complete, measurable, self-improving system ready for portfolio deployment.

---

## 3 — REPOSITORY STRUCTURE (TARGET STATE)

```
self-improving-agent/
├── agent/                              # Core agent package
│   ├── __init__.py                     # Package init — version string
│   ├── core/                           # Central harness components
│   │   ├── __init__.py                 # Exports: StateMachine, CircuitBreaker, Harness, ContextManager, Budget, TrajectoryLogger
│   │   ├── state_machine.py            # 8-state FSM — Phase 1 (no changes)
│   │   ├── circuit_breaker.py          # Full triple-condition breaker — Phase 2 (no changes)
│   │   ├── harness.py                  # Main orchestration loop — Phase 1+2 base + Phase 3.1 multi-agent wiring
│   │   ├── context_manager.py          # Layered prompt builder — STUB Phase 1/2, FULL IMPL Phase 3.3
│   │   ├── budget.py                   # Per-task token/cost tracking — Phase 2 stub + Phase 3.7 full impl
│   │   └── trajectory.py              # JSONL trajectory logger — Phase 1 base + Phase 3.11 replay/export
│   ├── agents/                         # Specialized sub-agents
│   │   ├── __init__.py                 # Exports: ArchitectAgent, WorkerAgent, JudgeAgent
│   │   ├── architect.py                # Planner + TaskDAG — created Phase 3.1 + Phase 3.2
│   │   ├── worker.py                   # Coder — Phase 1 base + Phase 3.1 upgrade
│   │   ├── judge.py                    # Reviewer — created Phase 3.1
│   │   └── protocol.py                # AgentMessage dataclass — Phase 1 base + Phase 3.1 update
│   ├── memory/                         # 4-layer memory system
│   │   ├── __init__.py                 # Exports: WorkingMemory, SessionMemory, IndexedMemory, FailureMemory, DreamEngine, DistillEngine
│   │   ├── working.py                  # Layer 1: In-process RAM — Phase 1 (no changes)
│   │   ├── session.py                  # Layer 2: MEMORY.md + checkpoint — Phase 2 (no changes)
│   │   ├── indexed.py                  # Layer 3: SQLite FTS5 — Phase 2 (no changes)
│   │   ├── failure.py                  # Layer 4: ChromaDB vectors — Phase 2 (no changes)
│   │   ├── dream.py                    # /dream maintenance — created Phase 3.5
│   │   └── distill.py                  # /distill skill extraction — created Phase 3.6
│   ├── tools/                          # Agent-Computer Interface + execution
│   │   ├── __init__.py                 # Package init
│   │   ├── aci.py                      # 7 curated tools — Phase 1 (no changes)
│   │   ├── sandbox.py                  # Docker sandbox — Phase 1 (no changes)
│   │   ├── repo_map.py                 # Tree-sitter structural index — Phase 2 (no changes)
│   │   ├── fault_localizer.py          # 3-level funnel — Phase 2 (no changes)
│   │   ├── fix_searcher.py             # Multi-candidate fix search — created Phase 3.4
│   │   ├── git_tools.py                # GitPython auto-commit — created Phase 3.9
│   │   └── mcp.py                      # MCP server registry — created Phase 3.8
│   ├── safety/                         # Permission and analysis gates
│   │   ├── __init__.py                 # Package init
│   │   ├── permissions.py              # 3-mode permission gate — Phase 2 (no changes)
│   │   └── static_analysis.py          # ruff + mypy + bandit runner — Phase 2 (no changes)
│   └── reflection/                     # Structured reflection pipeline
│       ├── __init__.py                 # Package init
│       └── engine.py                   # 6-step reflection — Phase 2 (no changes)
├── providers/                          # External service abstractions
│   ├── __init__.py                     # Package init
│   ├── llm.py                          # LiteLLM wrapper — Phase 1 (no changes)
│   └── embeddings.py                   # Embedding provider — Phase 2 (no changes)
├── ui/                                 # User interface
│   ├── __init__.py                     # Package init
│   ├── cli.py                          # Typer CLI — Phase 1+2 base + Phase 3 new commands
│   └── display.py                      # Rich status display — Phase 1 + Phase 3.12 loading states
├── eval/                               # Evaluation harness
│   ├── __init__.py                     # Package init
│   ├── harness.py                      # Benchmark runner — created Phase 3.10
│   ├── tasks/                          # 20 curated problems
│   │   ├── reverse_string.yaml         # Easy task
│   │   ├── stack_class.yaml            # Easy task
│   │   ├── linked_list.yaml            # Medium task
│   │   ├── binary_search.yaml          # Medium task
│   │   ├── rest_api.yaml               # Hard task
│   │   └── ... (15 more)              # Mix of easy/medium/hard
│   └── results/                        # JSON result files (gittracked)
│       └── .gitkeep
├── config/                             # Configuration
│   ├── default.yaml                    # Agent behavior config — Phase 1 + Phase 3.8 MCP section
│   └── models.yaml                     # Model routing table — Phase 1 (no changes)
├── memory/                             # Runtime memory directory
│   ├── MEMORY.md                       # Long-term verified facts — Phase 2
│   ├── checkpoint.md                   # Current state snapshot — Phase 2
│   ├── notes.md                        # Temporary scratchpad — Phase 2
│   ├── task_logs/                      # Per-task execution history — Phase 2
│   │   └── archive/                    # Compressed old logs — created by /dream
│   ├── memory_index.db                 # SQLite FTS5 database — Phase 2
│   ├── chromadb/                       # ChromaDB persistent storage — Phase 2
│   ├── skills/                         # Extracted skills — created Phase 3.6
│   └── trajectory_logs/               # JSONL trajectory files — Phase 1
├── docker/                             # Docker configuration
│   └── Dockerfile.sandbox              # Hardened sandbox image — Phase 1+2 + Phase 3.14 non-root user
├── tests/                              # Unit and integration tests
│   ├── __init__.py                     # auto-generated
│   ├── conftest.py                     # Shared fixtures — Phase 1+2 + Phase 3 additions
│   ├── test_state_machine.py           # FSM tests — Phase 1 (no changes)
│   ├── test_circuit_breaker.py         # Circuit breaker tests — Phase 1+2 (no changes)
│   ├── test_memory.py                  # Working memory tests — Phase 1 (no changes)
│   ├── test_session_memory.py          # Session memory tests — Phase 2 (no changes)
│   ├── test_indexed_memory.py          # FTS5 tests — Phase 2 (no changes)
│   ├── test_failure_memory.py          # ChromaDB tests — Phase 2 (no changes)
│   ├── test_reflection.py             # Reflection pipeline tests — Phase 2 (no changes)
│   ├── test_repo_map.py               # Tree-sitter tests — Phase 2 (no changes)
│   ├── test_fault_localizer.py         # Fault localization tests — Phase 2 (no changes)
│   ├── test_permissions.py             # Permission gate tests — Phase 2 (no changes)
│   ├── test_static_analysis.py         # Static analysis tests — Phase 2 (no changes)
│   ├── test_sandbox.py                 # Docker sandbox tests — Phase 1 (no changes)
│   ├── test_tools.py                   # ACI tool tests — Phase 1 (no changes)
│   ├── test_llm.py                     # LLM provider tests — Phase 1 (no changes)
│   ├── test_architect.py               # Architect + DAG tests — created Phase 3.1/3.2
│   ├── test_judge.py                   # Judge agent tests — created Phase 3.1
│   ├── test_worker.py                  # Worker agent tests — created Phase 3.1
│   ├── test_context_manager.py         # Context compaction tests — created Phase 3.3
│   ├── test_fix_searcher.py            # Multi-candidate tests — created Phase 3.4
│   ├── test_dream.py                   # /dream tests — created Phase 3.5
│   ├── test_distill.py                 # /distill tests — created Phase 3.6
│   ├── test_budget.py                  # Budget system tests — created Phase 3.7
│   ├── test_mcp.py                     # MCP tests — created Phase 3.8
│   ├── test_git.py                     # Git integration tests — created Phase 3.9
│   ├── test_eval_harness.py            # Eval harness tests — created Phase 3.10
│   └── test_e2e.py                     # End-to-end integration tests — created Phase 3.15
├── pyproject.toml                      # Project metadata — Phase 1+2 + Phase 3 new deps
├── README.md                           # Complete portfolio README — created Phase 3.13
├── .env.example                        # Env var template — Phase 1 + Phase 3 additions
├── .gitignore                          # Git ignore rules — Phase 1+2 (no changes)
└── tracker.md                          # Dynamic project status — updated continuously
```

---

## 4 — GLOBAL CONSTRAINTS

1. **Python 3.11+ only.** All code must use `match` statements, `StrEnum`, `Self` type, `ExceptionGroup`, and `TaskGroup` where appropriate.
2. **Pydantic v2 for all data models.** Every dataclass-like structure must be a `pydantic.BaseModel`. No raw `@dataclass` from stdlib.
3. **`mypy --strict` must pass at all times.** No `# type: ignore` without an inline comment explaining why.
4. **`ruff check` must pass at all times.** Line length = 100. Target version = py311.
5. **LiteLLM model strings must include the provider prefix.** `gemini/gemini-2.0-flash`, NOT `gemini-2.0-flash`.
6. **Docker containers must ALWAYS be cleaned up in `finally` blocks.**
7. **All async code uses `asyncio`.** No threading, no multiprocessing, no external async frameworks.
8. **File writes are atomic.** Write to `.tmp` file, then `os.rename()`.
9. **The FSM is the single source of truth for agent state.**
10. **Tool execution always goes through `ToolRegistry.execute()`.**
11. **Secrets live in `.env` only.**
12. **All LLM calls go through `LLMProvider`.**
13. **`uv` is the only package manager.**
14. **Every public function has a docstring.**
15. **Multi-agent communication uses typed `AgentMessage` objects.** No raw strings passed between agents. Every inter-agent message is a structured Pydantic model with `from_agent`, `to_agent`, `message_type`, `content`, and `confidence`.
16. **The Architect NEVER writes code.** It produces plans (TaskDAG). The Worker NEVER plans. It executes tool calls from plans. The Judge NEVER writes or plans. It reviews. Separation is absolute.
17. **Judge override rules are hard-coded in the harness.** `rejected + confidence > 0.7` = Worker revises. `rejected + confidence <= 0.7` = proceed to tests. Max 2 overrides per iteration.
18. **Context compaction preserves ALL file paths and error messages verbatim.** Only verbose tool outputs and intermediate code are summarized. Compaction NEVER loses signal.
19. **Git operations use `git add <specific files>`, NEVER `git add -a` or `git commit -a`.** The agent must never commit the user's uncommitted changes.
20. **MCP tools are prefixed with the server name.** If the GitHub MCP server exposes `create_issue`, it becomes `github.create_issue` in the ToolRegistry. No name collisions with built-in tools.
21. **All Phase 1 and Phase 2 tests must continue passing.** Phase 3 must not break any existing functionality.

---

## 5 — INTERFACES AND TYPES (MASTER REFERENCE)

### 5.1 Multi-Agent Protocol Types (Phase 3 UPGRADE)

```python
# agent/agents/protocol.py — UPGRADED IN PHASE 3

from enum import StrEnum
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any

class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    ARCHITECT = "architect"
    WORKER = "worker"
    JUDGE = "judge"

class MessageType(StrEnum):
    PLAN = "plan"
    CODE = "code"
    REVIEW = "review"
    REFLECTION = "reflection"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    VERDICT = "verdict"                  # NEW Phase 3
    REVISION_REQUEST = "revision_request"  # NEW Phase 3
    FEEDBACK = "feedback"                # NEW Phase 3

class AgentMessage(BaseModel):
    from_agent: AgentRole
    to_agent: AgentRole
    message_type: MessageType
    content: str
    confidence: float = 1.0
    iteration: int = 0                   # NEW Phase 3
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = {}
```

### 5.2 Architect Types (NEW Phase 3)

```python
# agent/agents/architect.py

from pydantic import BaseModel

class SubTask(BaseModel):
    """Single unit of work in a DAG plan."""
    task_id: str
    description: str
    depends_on: list[str] = []           # task_ids this depends on
    status: str = "pending"              # pending | in_progress | done | failed
    estimated_complexity: str = "medium" # easy | medium | hard
    files_to_create: list[str] = []
    files_to_modify: list[str] = []
    result: dict | None = None           # Stored result after completion

class TaskDAG(BaseModel):
    """Directed Acyclic Graph of subtasks."""
    tasks: list[SubTask] = []

    def validate_dag(self) -> bool:
        """Topological sort to detect cycles. Check all deps valid. Check entry points exist."""
        ...

    def get_ready_tasks(self) -> list[SubTask]:
        """Tasks where ALL dependencies have status 'done'."""
        ...

    def mark_done(self, task_id: str, result: dict) -> None:
        """Update task status to 'done', store result."""
        ...

    def mark_failed(self, task_id: str, error: str) -> None:
        """Update task status to 'failed'."""
        ...

    def get_downstream(self, task_id: str) -> list[SubTask]:
        """All tasks that depend on this one (directly or transitively)."""
        ...

    def is_complete(self) -> bool:
        """All tasks done."""
        ...

    def replan_branch(self, failed_task_id: str, new_subtasks: list[SubTask]) -> None:
        """Replace failed task + downstream with new subtasks. Preserve completed."""
        ...
```

### 5.3 Worker Types (Phase 3 UPGRADE)

```python
# agent/agents/worker.py

from pydantic import BaseModel

class CodeResult(BaseModel):
    """Result from Worker executing a subtask."""
    files_modified: list[str] = []
    files_created: list[str] = []
    tool_calls_made: list[dict] = []
    tokens_used: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: str | None = None
```

### 5.4 Judge Types (NEW Phase 3)

```python
# agent/agents/judge.py

from pydantic import BaseModel

class Verdict(BaseModel):
    """Judge's review of code changes."""
    approved: bool
    confidence: float = 0.5             # 0.0 to 1.0
    issues: list[str] = []              # Specific issues found
    suggestions: list[str] = []         # Improvement suggestions
    reasoning: str = ""                 # Why approved/rejected
```

### 5.5 Context Compaction Types (NEW Phase 3)

```python
# agent/core/context_manager.py

from pydantic import BaseModel

class Message(BaseModel):
    """A single message in the conversation history."""
    role: str                            # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None              # Tool name for tool messages
    token_count: int = 0                 # Cached token count

class CompactionResult(BaseModel):
    """Result from context compaction."""
    summary: str                         # Compressed history
    preserved_paths: list[str] = []      # All file paths (never summarized away)
    preserved_errors: list[str] = []     # All error messages (never summarized away)
    preserved_decisions: list[str] = []  # All architectural decisions
    tokens_saved: int = 0               # How many tokens freed
```

### 5.6 Fix Searcher Types (NEW Phase 3)

```python
# agent/tools/fix_searcher.py

from pydantic import BaseModel

class CodeEdit(BaseModel):
    """A single code edit within a patch."""
    file: str
    start_line: int
    end_line: int
    new_content: str

class CodePatch(BaseModel):
    """A complete fix candidate with test results."""
    edits: list[CodeEdit] = []
    tests_passed: int = 0
    tests_failed: int = 0
    lint_errors: int = 0
    confidence: float = 0.0
    candidate_id: int = 0               # Which candidate (1, 2, 3)
```

### 5.7 Dream Types (NEW Phase 3)

```python
# agent/memory/dream.py

from pydantic import BaseModel

class DreamReport(BaseModel):
    """Report from /dream memory maintenance."""
    duplicates_merged: int = 0
    paths_validated: int = 0
    stale_paths: int = 0
    logs_compressed: int = 0
    failures_pruned: int = 0
    total_entries_after: int = 0
    summary: str = ""                    # Human-readable 1-paragraph summary
```

### 5.8 Distill Types (NEW Phase 3)

```python
# agent/memory/distill.py

from pydantic import BaseModel

class Skill(BaseModel):
    """An extracted reusable skill template."""
    name: str                            # e.g., "fix_import_error"
    description: str                     # What this skill does
    trigger_pattern: str = ""            # When to activate this skill
    steps: list[dict] = []               # Templatized steps with {{placeholders}}
    source_tasks: list[str] = []         # Task IDs this was extracted from
    generality_score: float = 0.0        # 0.0 (project-specific) to 1.0 (universal)
    created_at: str = ""
```

### 5.9 Budget Types (Phase 3 FULL IMPL)

```python
# agent/core/budget.py

from pydantic import BaseModel

class BudgetReport(BaseModel):
    """Detailed budget usage report."""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    max_tokens: int = 100000
    max_cost_usd: float = 0.50
    token_percent: float = 0.0
    cost_percent: float = 0.0
    per_model_breakdown: dict = {}       # model → {tokens, cost}
    per_state_breakdown: dict = {}       # state → {tokens, cost}
    warning_threshold_hit: bool = False  # True if > 80%

class BudgetExhaustedError(Exception):
    """Raised when budget is exceeded."""
    def __init__(self, report: BudgetReport):
        self.report = report
        super().__init__(f"Budget exhausted: {report.cost_percent:.0f}% cost, {report.token_percent:.0f}% tokens")
```

### 5.10 MCP Types (NEW Phase 3)

```python
# agent/tools/mcp.py

from pydantic import BaseModel

class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    name: str                            # e.g., "github", "filesystem"
    command: str                         # e.g., "npx"
    args: list[str] = []                 # Command arguments
    env: dict[str, str] = {}             # Environment variables

class MCPToolDefinition(BaseModel):
    """A tool discovered from an MCP server."""
    server_name: str
    tool_name: str                       # Original name from MCP
    qualified_name: str                  # "{server_name}.{tool_name}"
    description: str
    parameters: dict = {}                # JSON Schema
```

### 5.11 Git Types (NEW Phase 3)

```python
# agent/tools/git_tools.py

from pydantic import BaseModel

class CommitInfo(BaseModel):
    """Information about a git commit made by the agent."""
    sha: str
    message: str
    files_changed: list[str] = []
    task_id: str = ""
    timestamp: str = ""
```

### 5.12 Evaluation Types (NEW Phase 3)

```python
# eval/harness.py

from pydantic import BaseModel

class EvalTask(BaseModel):
    """A single evaluation task definition."""
    id: str                              # e.g., "reverse_string"
    difficulty: str                      # "easy" | "medium" | "hard"
    description: str                     # The goal to give the agent
    test_file: str                       # Path to test file
    expected_files: list[str] = []       # Files the agent should create
    max_iterations: int = 5
    timeout_seconds: int = 300

class EvalResult(BaseModel):
    """Result of running one eval task."""
    task_id: str
    solved: bool
    iterations: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    error: str | None = None

class EvalReport(BaseModel):
    """Aggregated evaluation results."""
    results: list[EvalResult] = []
    solve_rate: float = 0.0              # Percentage solved
    avg_iterations: float = 0.0
    avg_cost: float = 0.0
    avg_time: float = 0.0
    per_difficulty: dict = {}            # {difficulty: {solve_rate, avg_cost, ...}}
    timestamp: str = ""
```

---

## 6 — PHASES (THE BUILD PLAN)

---

### PHASE 3.1 — ARCHITECT / WORKER / JUDGE PIPELINE

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2 complete
**ESTIMATED DURATION:** 4.5 hours
**GOAL:** Three specialized sub-agents — Architect (plans with strong model), Worker (codes with fast model + tools), Judge (reviews with strong model) — communicating via typed `AgentMessage` objects with confidence-based override rules.

#### FILES TO CREATE:

##### `agent/agents/architect.py`
- **`ArchitectAgent` class:**
  - `__init__(llm: LLMProvider, repo_map: RepoMap, failure_memory: FailureMemory)`:
    - Store references
    - Uses strong model (`task_type="planning"`)
  - `async plan(goal: str, repo_map_str: str, memories: list[str], fault_locations: list[EditLocation] | None = None) -> TaskDAG`:
    - Build prompt:
      - System: "You are an expert software architect. Decompose the goal into a DAG of subtasks."
      - Include: goal, repo map, relevant memories from MEMORY.md, fault locations (if bug-fix)
      - Include: existing skills from `memory/skills/` if matching (retrieved via embedding similarity)
    - Request structured output: `TaskDAG` (Pydantic response_format)
    - Validate DAG: call `dag.validate_dag()`. If invalid (cyclic), retry up to 2 times.
    - Each SubTask includes: id, description, dependencies, estimated_complexity, files_to_create, files_to_modify
    - Return validated `TaskDAG`
  - `async replan_on_failure(dag: TaskDAG, failed_task: SubTask, error: ErrorSignature) -> TaskDAG`:
    - Identify all downstream dependents of failed task
    - Keep completed tasks untouched
    - Replan only the failed subtask + downstream
    - Return updated `TaskDAG`
  - **Constraint:** Does NOT write code. Planning only.

##### `agent/agents/worker.py` (UPGRADE)
- **`WorkerAgent` class:**
  - `__init__(llm: LLMProvider, tools: ToolRegistry)`:
    - Store references
    - Uses fast model (`task_type="coding"`)
  - `async execute(subtask: SubTask, context: str) -> CodeResult`:
    - Build prompt:
      - System: "You are an expert coder. Use the provided tools to implement the subtask."
      - Include: subtask description, relevant file contents, architect's plan context
      - Include: tool definitions (`self.tools.get_tool_definitions()`)
    - Parse LLM response for tool calls (function-calling format)
    - Execute each tool call via `self.tools.execute(tool_name, params, mode=AgentMode.BUILD)`
    - Accumulate `files_modified`, `files_created`, `tool_calls_made`
    - Return `CodeResult`
  - `async fix_lint(lint_errors: list[LintError]) -> CodeResult`:
    - Feed lint errors to LLM with fast model (`task_type="lint_fix"`)
    - Generate targeted `edit_file` tool calls
    - Execute and return
  - `async revise(code_result: CodeResult, verdict: Verdict) -> CodeResult`:
    - Feed Judge's issues and suggestions
    - Generate corrective edits
    - Return updated `CodeResult`

##### `agent/agents/judge.py`
- **`JudgeAgent` class:**
  - `__init__(llm: LLMProvider)`:
    - Uses strong model (`task_type="judge_review"`)
  - `async review(code_changes: CodeResult, plan: SubTask, tests_exist: bool) -> Verdict`:
    - Read the actual content of modified/created files
    - Build prompt:
      - System: "You are a code reviewer. Check for correctness, edge cases, error handling, code quality, and security."
      - Include: the plan (subtask description), the actual code changes, whether tests exist
    - Request structured output: `Verdict` (Pydantic)
    - Return `Verdict`
  - **Override rules (enforced by harness, not Judge):**
    - `approved == False AND confidence > 0.7` → Worker MUST revise
    - `approved == False AND confidence <= 0.7` → proceed to testing (tests are arbiter)
    - Max 2 judge overrides per iteration → proceed to testing regardless

##### `tests/test_architect.py`
- `test_plan_generates_valid_dag`: Mock LLM, verify TaskDAG returned with valid structure
- `test_plan_includes_subtask_dependencies`: Verify dependencies are populated
- `test_plan_retries_on_cyclic_dag`: Mock LLM returning cyclic DAG then valid, verify retry
- `test_replan_preserves_completed`: Complete 2 tasks, fail 3rd, replan, verify first 2 preserved
- `test_single_task_goal`: Simple goal → DAG with 1 task + 1 verification task

##### `tests/test_judge.py`
- `test_judge_approves_good_code`: Mock LLM returning approval, verify Verdict.approved = True
- `test_judge_rejects_bad_code`: Mock LLM returning rejection, verify issues populated
- `test_verdict_has_confidence`: Verify confidence field is set
- `test_verdict_has_issues_and_suggestions`: Verify structured feedback

##### `tests/test_worker.py`
- `test_worker_executes_tool_calls`: Mock LLM returning tool calls, verify execution
- `test_worker_returns_code_result`: Verify CodeResult fields populated
- `test_worker_fix_lint`: Feed lint errors, verify corrective edits
- `test_worker_revise_from_verdict`: Feed verdict with issues, verify revisions

#### FILES TO MODIFY:

##### `agent/core/harness.py`
- Update main loop to use the 3-agent pipeline:
  - PLANNING: `architect.plan()` instead of direct LLM call
  - CODING: Iterate through TaskDAG using `worker.execute()` for each ready subtask
  - After CODING: `judge.review()` → apply override rules → revise or proceed
  - REFLECTING: `architect.replan_on_failure()` if a subtask fails

##### `agent/agents/protocol.py`
- Add `VERDICT`, `REVISION_REQUEST`, `FEEDBACK` to `MessageType` enum
- Add `iteration` field to `AgentMessage`

#### ACCEPTANCE CRITERIA:

- [ ] Architect generates a valid TaskDAG with subtasks and dependencies
- [ ] Worker executes subtasks using tools and returns CodeResult
- [ ] Judge reviews code and returns structured Verdict
- [ ] Override rules are enforced: high-confidence rejection → revision, low-confidence → proceed
- [ ] Max 2 overrides per iteration (prevents infinite revision loop)
- [ ] `replan_on_failure()` preserves completed work
- [ ] All new test cases pass (5 + 4 + 4 = 13)
- [ ] All Phase 1+2 tests still pass
- [ ] `ruff check agent/` returns 0 errors
- [ ] `mypy agent/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_architect.py tests/test_judge.py tests/test_worker.py -v` — all pass
2. Run `uv run agent run "Write a function that reverses a string and write tests"` — verify Architect/Worker/Judge cycle in verbose output
3. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT let the Architect write code. It produces `TaskDAG` ONLY.
- Do NOT let the Worker plan. It receives a `SubTask` and executes tools.
- Do NOT let the Judge write code or plan. It produces `Verdict` ONLY.
- Do NOT allow more than 2 judge overrides. After 2 rejections, proceed to testing regardless.
- Do NOT pass raw strings between agents. Use typed `AgentMessage` objects.

---

### PHASE 3.2 — DAG-BASED TASK PLANNING

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 3.1 (Architect agent)
**ESTIMATED DURATION:** 2.5 hours
**GOAL:** A fully validated `TaskDAG` class with topological sort, cycle detection, ready-task dispatch, completion tracking, and branch replanning — enabling the agent to decompose complex goals into ordered subtasks.

#### FILES TO MODIFY:

##### `agent/agents/architect.py` — implement `TaskDAG` methods:
- `validate_dag() -> bool`:
  - Topological sort via Kahn's algorithm: build in-degree map, process zero-in-degree nodes
  - If any nodes remain after processing: cycle detected → return False
  - Check all dependency IDs reference valid task_ids
  - Check at least one task has `depends_on == []` (entry point)
  - Remove orphan tasks (no path from any entry point)
  - Return True if valid
- `get_ready_tasks() -> list[SubTask]`:
  - Return tasks where `status == "pending"` AND all dependencies have `status == "done"`
- `mark_done(task_id: str, result: dict)`:
  - Find task, set `status = "done"`, store `result`
- `mark_failed(task_id: str, error: str)`:
  - Find task, set `status = "failed"`
- `get_downstream(task_id: str) -> list[SubTask]`:
  - BFS/DFS from task_id following dependency edges (reverse direction)
  - Return all transitively dependent tasks
- `is_complete() -> bool`:
  - Return `all(t.status == "done" for t in self.tasks)`
- `replan_branch(failed_task_id: str, new_subtasks: list[SubTask])`:
  - Get downstream tasks of failed task
  - Remove failed task + downstream from `self.tasks`
  - Add `new_subtasks` (which should reference existing completed tasks as dependencies)
  - Re-validate DAG
- **Phase 3 simplification:** Sequential execution of ready tasks (not parallel). Parallel is a future optimization.

##### `tests/test_architect.py` (ADD NEW TESTS)
- `test_validate_detects_cycle`: Create DAG with cycle, verify validate returns False
- `test_validate_detects_missing_dependency`: Reference nonexistent task_id, verify False
- `test_validate_requires_entry_point`: All tasks have dependencies, verify False
- `test_get_ready_tasks_returns_entry_points`: Verify only zero-dependency tasks returned initially
- `test_get_ready_tasks_after_completion`: Mark first task done, verify second becomes ready
- `test_mark_done_stores_result`: Verify result is stored on task
- `test_get_downstream_finds_all`: 3-task chain A→B→C, verify downstream(A) = [B, C]
- `test_is_complete_all_done`: Mark all tasks done, verify True
- `test_is_complete_partial`: Leave one pending, verify False
- `test_replan_branch_preserves_completed`: Complete A, fail B, replan, verify A untouched
- `test_empty_dag_raises_error`: Empty tasks list → error

#### ACCEPTANCE CRITERIA:

- [ ] Topological sort detects cycles correctly
- [ ] Missing dependencies are caught during validation
- [ ] `get_ready_tasks()` returns correct tasks based on completion status
- [ ] `get_downstream()` returns all transitively dependent tasks
- [ ] `replan_branch()` preserves completed work and replaces only the failed branch
- [ ] All 16 test cases pass (5 from Phase 3.1 + 11 new)
- [ ] All Phase 1+2 tests still pass
- [ ] `ruff check agent/agents/` returns 0 errors
- [ ] `mypy agent/agents/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_architect.py -v` — all 16 tests pass
2. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT implement parallel execution of ready tasks. Sequential only for Phase 3.
- Do NOT forget to handle empty DAGs (raise an error, don't return silently).
- Do NOT use recursive DFS for cycle detection — use Kahn's algorithm (iterative) to avoid stack overflow on large DAGs.
- Do NOT mutate the original DAG during validation. Work on a copy.

---

### PHASE 3.3 — CONTEXT COMPACTION

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.2 (LLMProvider)
**ESTIMATED DURATION:** 2.5 hours
**GOAL:** A `ContextManager` that builds the LLM context window in 6 prioritized layers, compacts at 60% utilization, and preserves all file paths and error messages during summarization.

#### FILES TO CREATE/MODIFY:

##### `agent/core/context_manager.py` (FULL IMPLEMENTATION — replace stub)
- **`Message` BaseModel:** role, content, name, token_count
- **`CompactionResult` BaseModel:** summary, preserved_paths, preserved_errors, preserved_decisions, tokens_saved
- **`ContextManager` class:**
  - `__init__(llm: LLMProvider, max_tokens: int = 128_000, compaction_threshold: float = 0.6)`:
    - Store config
    - `self._compacted_history: str = ""`
  - `build_context(system_prompt: str, tool_defs: str, memory: str, repo_map: str, history: list[Message]) -> list[dict]`:
    - Layer 1 (static): system prompt — always first for KV cache hits
    - Layer 2 (static): tool definitions — 7 tool JSON schemas
    - Layer 3 (semi-static): MEMORY.md contents
    - Layer 4 (semi-static): repo map from tree-sitter
    - Layer 5 (dynamic): compacted history summary (if compaction has occurred)
    - Layer 6 (dynamic): last 3 exchanges verbatim (always full-fidelity)
    - Count total tokens via `estimate_tokens()`
    - If total > `max_tokens * compaction_threshold`: trigger `compact()`
    - Return as list of `{"role": ..., "content": ...}` dicts for LLM
  - `async compact(messages: list[Message]) -> CompactionResult`:
    - Keep: system prompt, repo map, last 3 exchanges, active plan, active errors
    - Summarize: everything older than last 3 exchanges
    - Use cheap model (`task_type="context_compaction"`)
    - Prompt: "Summarize the following conversation history. PRESERVE: all file paths, error messages, resolutions, architectural decisions. DISCARD: verbose tool outputs, intermediate code, repetitive text."
    - Extract preserved paths/errors/decisions from the summary
    - Store compacted summary in `self._compacted_history`
    - Return `CompactionResult`
  - `estimate_tokens(text: str) -> int`:
    - Try `tiktoken`: `encoding = tiktoken.encoding_for_model("gpt-4"); return len(encoding.encode(text))`
    - Fallback: `return len(text) // 4` (heuristic: 1 token ≈ 4 chars)
    - Apply 10% safety margin (overcount)

##### `tests/test_context_manager.py`
- `test_build_context_layer_order`: Verify system prompt is first, tool defs second, etc.
- `test_build_context_includes_all_layers`: Verify all 6 layers present
- `test_compaction_triggers_at_threshold`: Fill context to 61%, verify compaction runs
- `test_compaction_does_not_trigger_below_threshold`: Fill to 50%, verify no compaction
- `test_compaction_preserves_file_paths`: Compact history with paths, verify paths in result
- `test_compaction_preserves_error_messages`: Compact history with errors, verify preserved
- `test_last_3_exchanges_kept_verbatim`: Verify last 3 messages not summarized
- `test_estimate_tokens_heuristic`: Verify heuristic produces reasonable count
- `test_compaction_uses_cheap_model`: Mock LLM, verify task_type="context_compaction"

#### ACCEPTANCE CRITERIA:

- [ ] Context is built in correct layer order (static first for cache hits)
- [ ] Compaction triggers at 60% utilization threshold
- [ ] File paths and error messages are preserved during compaction
- [ ] Last 3 exchanges are always kept verbatim
- [ ] Token estimation produces reasonable results
- [ ] All 9 test cases pass
- [ ] All Phase 1+2 tests still pass
- [ ] `ruff check agent/core/` returns 0 errors
- [ ] `mypy agent/core/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_context_manager.py -v` — all pass
2. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT compact too aggressively. Every compaction invalidates the LLM's KV cache. The 60% threshold balances cache hit rate vs. token savings.
- Do NOT summarize away file paths or error messages. These are the primary signals the agent uses for debugging.
- Do NOT use an expensive model for compaction. Use the fast/cheap model (`context_compaction` task type).
- Do NOT forget the 10% safety margin on token estimation. Underestimating causes context overflow.

---

### PHASE 3.4 — MULTI-CANDIDATE FIX SEARCH

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2.7 (FaultLocalizer + EditLocation), Phase 2.10 (StaticAnalyzer), Phase 1.4 (DockerSandbox)
**ESTIMATED DURATION:** 3 hours
**GOAL:** A `FixSearcher` that generates N fix candidates with temperature > 0, tests each in the sandbox, and returns the best one — dramatically increasing first-pass solve rate.

#### FILES TO CREATE:

##### `agent/tools/fix_searcher.py`
- **`CodeEdit` BaseModel:** file, start_line, end_line, new_content
- **`CodePatch` BaseModel:** edits, tests_passed, tests_failed, lint_errors, confidence, candidate_id
- **`FixSearcher` class:**
  - `__init__(llm: LLMProvider, sandbox: DockerSandbox, analyzer: StaticAnalyzer)`:
    - Store references
  - `async search(error: ErrorSignature, locations: list[EditLocation], workspace_dir: str, n: int = 3) -> CodePatch | None`:
    - Read code at each edit location
    - Generate N fix candidates using LLM with `temperature=0.7` (diversity):
      - Prompt: "Generate a fix for this error. Return the exact code changes."
      - Each call uses same prompt but different temperature sampling
    - For each candidate:
      - Copy workspace to temp directory
      - Apply the patch edits to temp copy
      - Run static analysis (ruff + mypy): filter out candidates that introduce NEW lint errors
      - Run pytest in sandbox: count passing/failing
    - Rank candidates: most tests passing wins. Tiebreaker: fewest lint warnings.
    - Return best candidate, or None if ALL candidates fail worse than current state
  - `async _generate_candidate(error: ErrorSignature, locations: list[EditLocation], code_context: str, candidate_num: int) -> CodePatch`:
    - Build prompt with error + code at locations
    - Call LLM with `temperature=0.7`
    - Parse response into `CodePatch`
  - `async _test_candidate(patch: CodePatch, workspace_dir: str) -> CodePatch`:
    - Apply patch to temp copy
    - Run lint → count errors
    - Run tests → count pass/fail
    - Return updated `CodePatch` with test results

##### `tests/test_fix_searcher.py`
- `test_search_returns_best_candidate`: Mock 3 candidates, one with most tests passing, verify it's returned
- `test_search_returns_none_when_all_fail`: Mock all candidates failing, verify None
- `test_candidate_generation_uses_temperature`: Mock LLM, verify temperature=0.7
- `test_lint_filter_excludes_bad_candidates`: Candidate introduces new lint errors, verify filtered
- `test_ranking_tiebreaker_fewest_lint`: Two candidates with same tests passing, verify fewer lint wins
- `test_sandbox_timeout_skips_candidate`: Candidate causes sandbox timeout, verify skipped
- `test_cost_tracking`: Verify N candidates cost is tracked in budget

#### ACCEPTANCE CRITERIA:

- [ ] N candidates are generated with diversity (temperature > 0)
- [ ] Each candidate is tested independently in sandbox
- [ ] Best candidate (most tests passing) is returned
- [ ] Candidates introducing new lint errors are filtered
- [ ] None is returned when all candidates are worse than current state
- [ ] Sandbox timeouts skip the candidate (don't crash)
- [ ] All 7 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_fix_searcher.py -v` — all pass
2. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT use temperature=0 for candidate generation. The whole point is diversity — `temperature=0.7`.
- Do NOT test candidates in the actual workspace. Copy to temp directory first.
- Do NOT forget cleanup of temp directories. Use `try/finally`.
- Do NOT forget to account for N× cost in the budget tracker. 3 candidates = 3× LLM cost + 3× sandbox cost.

---

### PHASE 3.5 — `/DREAM` MEMORY MAINTENANCE

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2.1 (SessionMemory), Phase 2.2 (IndexedMemory), Phase 2.3 (FailureMemory + EmbeddingProvider)
**ESTIMATED DURATION:** 3 hours
**GOAL:** A `DreamEngine` that performs 7-step memory maintenance — deduplicate, validate paths, compress old logs, prune stale failures, reindex — keeping the agent's memory lean and accurate.

#### FILES TO CREATE:

##### `agent/memory/dream.py`
- **`DreamReport` BaseModel:** duplicates_merged, paths_validated, stale_paths, logs_compressed, failures_pruned, total_entries_after, summary
- **`DreamEngine` class:**
  - `__init__(session: SessionMemory, indexed: IndexedMemory, failure: FailureMemory, embeddings: EmbeddingProvider, llm: LLMProvider)`:
    - Store all references
  - `async run() -> DreamReport`:
    - Execute 7 steps in sequence, accumulate report metrics
    - Each step is idempotent (safe to re-run if interrupted)
  - **Step 1 — SCAN:** `_scan() -> dict`:
    - Read all memory files: MEMORY.md, notes.md, all task_logs
    - Count entries in FTS5 and ChromaDB
    - Return inventory dict
  - **Step 2 — DEDUPLICATE:** `async _deduplicate() -> int`:
    - Get all entries from FTS5
    - Compute embeddings for each (batch)
    - Pairwise cosine similarity: if > 0.92 → merge (keep the more detailed entry)
    - Delete the shorter/less detailed duplicate from FTS5
    - Return count of merges
  - **Step 3 — VALIDATE:** `_validate_paths() -> tuple[int, int]`:
    - Read MEMORY.md
    - For each entry mentioning a file path: check `os.path.exists(path)`
    - If not found: append `[PATH NOT FOUND]` warning to that entry
    - Return (total_validated, stale_count)
  - **Step 4 — COMPRESS:** `async _compress_old_logs(max_age_days: int = 7) -> int`:
    - List all task_logs older than `max_age_days`
    - For each: use cheap LLM to generate 1-paragraph summary
    - Move original to `memory/task_logs/archive/`
    - Write summary to `memory/task_logs/{task_id}.md`
    - Return count of compressed logs
  - **Step 5 — PRUNE:** `_prune_failures(max_age_days: int = 30) -> int`:
    - Call `self.failure.prune(max_age_days=max_age_days)`
    - Delete ChromaDB records where: `success == False` AND age > max_age_days AND never retrieved
    - Return count of pruned records
  - **Step 6 — REINDEX:** `_reindex() -> None`:
    - Call `self.indexed.reindex_from_markdown(self.session)`
    - Rebuild FTS5 index from current MEMORY.md + task_logs
  - **Step 7 — REPORT:** `_generate_report(metrics: dict) -> DreamReport`:
    - Aggregate all step metrics
    - Generate 1-paragraph human-readable summary
    - Return `DreamReport`

##### `tests/test_dream.py`
- `test_scan_returns_inventory`: Create memory files, verify scan counts
- `test_deduplicate_merges_similar`: Create 2 near-identical entries, verify merged
- `test_deduplicate_keeps_detailed`: Merge short + detailed, verify detailed kept
- `test_validate_finds_stale_paths`: Reference nonexistent file in MEMORY.md, verify flagged
- `test_validate_valid_paths_untouched`: Reference existing file, verify no warning
- `test_compress_moves_old_logs`: Create old task log, compress, verify moved to archive
- `test_compress_preserves_recent_logs`: Create recent log, verify not compressed
- `test_prune_removes_old_failures`: Store old failed records, verify pruned
- `test_reindex_rebuilds_fts5`: Add entries to MEMORY.md, reindex, verify searchable
- `test_full_dream_returns_report`: Run full pipeline, verify DreamReport populated
- `test_empty_memory_no_crash`: Run dream on fresh install, verify "No memory to maintain"

#### ACCEPTANCE CRITERIA:

- [ ] Deduplication merges entries with similarity > 0.92
- [ ] Path validation flags stale paths without deleting entries
- [ ] Log compression moves old logs to archive and replaces with summaries
- [ ] Failure pruning removes old unsuccessful records
- [ ] Reindexing rebuilds FTS5 from Markdown sources
- [ ] Fresh install (no memory) doesn't crash
- [ ] All 11 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_dream.py -v` — all pass
2. Create some memory entries, run `/dream` via CLI, verify DreamReport output
3. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT delete entries during validation. Only append warnings. The fact might still be valuable even if the file moved.
- Do NOT embed all entries at once for deduplication. Use batch embedding to avoid OOM.
- Do NOT compress task logs younger than 7 days. They may still be actively referenced.
- Do NOT make any step non-idempotent. `/dream` must be safe to re-run after interruption.

---

### PHASE 3.6 — `/DISTILL` SKILL EXTRACTION

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 3.5 (DreamEngine for memory access patterns), Phase 2.3 (EmbeddingProvider)
**ESTIMATED DURATION:** 3 hours
**GOAL:** A `DistillEngine` that analyzes successful task trajectories, finds repeated patterns, and extracts reusable skill templates with placeholders — the core self-improvement mechanism.

#### FILES TO CREATE:

##### `agent/memory/distill.py`
- **`Skill` BaseModel:** name, description, trigger_pattern, steps, source_tasks, generality_score, created_at
- **`DistillEngine` class:**
  - `__init__(trajectory_logger: TrajectoryLogger, embeddings: EmbeddingProvider, llm: LLMProvider, failure_memory: FailureMemory)`:
    - Store references
  - `async run() -> list[Skill]`:
    - Execute 5-step algorithm
    - Return list of newly extracted skills
  - **Step 1 — PATTERN DETECTION:** `async _detect_patterns() -> list[list[str]]`:
    - Load all task trajectories
    - Group by goal similarity (embedding similarity > 0.85)
    - Require ≥ 3 SUCCESSFUL completions per cluster
    - Return clusters of task_ids
  - **Step 2 — EXTRACT COMMON STEPS:** `_extract_common_steps(cluster: list[str]) -> list[dict]`:
    - Load full trajectory for each task in cluster
    - Extract the sequence of tool calls that led to success
    - Find LCS (Longest Common Subsequence) across all trajectories
    - Identify invariant steps (always done) vs. variable steps
    - Return ordered list of common steps
  - **Step 3 — TEMPLATIZE:** `_templatize(common_steps: list[dict]) -> Skill`:
    - Replace specific values with `{{placeholders}}`:
      - File names → `{{target_file}}`
      - Function names → `{{function_name}}`
      - Error messages → `{{error_pattern}}`
    - Create skill files:
      - `memory/skills/{skill_name}.md` — human-readable description
      - `memory/skills/{skill_name}.yaml` — structured steps with placeholders
    - Return `Skill` object
  - **Step 4 — VALIDATE:** `async _validate(skill: Skill) -> Skill`:
    - Use LLM: "Is this skill general enough to be reusable, or too project-specific?"
    - Set `generality_score`: 0.0 (project-specific) to 1.0 (universal)
    - If general (> 0.5): add to global skill index
    - If project-specific: save but don't index globally
  - **Step 5 — INDEX & RETRIEVE:** `_index_skill(skill: Skill)`:
    - Add skill embedding to ChromaDB (separate collection: `skills`)
    - Future: Architect retrieves matching skills before planning

##### `tests/test_distill.py`
- `test_pattern_detection_groups_similar`: Create 3 similar successful trajectories, verify grouped
- `test_pattern_detection_requires_3_minimum`: Create 2 similar, verify NOT grouped
- `test_extract_common_steps_finds_lcs`: Create trajectories with common subsequence, verify extracted
- `test_templatize_replaces_filenames`: Verify file names replaced with `{{target_file}}`
- `test_templatize_replaces_function_names`: Verify function names replaced with `{{function_name}}`
- `test_validate_scores_generality`: Mock LLM, verify generality_score set
- `test_skill_files_created`: Run distill, verify `.md` and `.yaml` files in `memory/skills/`
- `test_insufficient_data_returns_empty`: < 3 successful completions, verify empty result with message

#### ACCEPTANCE CRITERIA:

- [ ] Pattern detection groups similar successful tasks (embedding similarity > 0.85)
- [ ] Requires ≥ 3 successful completions before extracting (cold start protection)
- [ ] Common steps are correctly extracted via LCS
- [ ] Templatization replaces specific values with `{{placeholders}}`
- [ ] LLM validates generality (general vs. project-specific)
- [ ] Skill files are created in `memory/skills/`
- [ ] All 8 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_distill.py -v` — all pass
2. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT extract skills from fewer than 3 successful completions. The pattern is not reliable enough.
- Do NOT hardcode file names or function names in skills. Everything specific must be a `{{placeholder}}`.
- Do NOT store skills only in memory. Write to `memory/skills/` as Markdown + YAML files that are human-readable and git-committable.

---

### PHASE 3.7 — COST/TOKEN BUDGET SYSTEM (FULL IMPLEMENTATION)

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.2 (LLMProvider cost tracking)
**ESTIMATED DURATION:** 2 hours
**GOAL:** A production `Budget` class that tracks per-model and per-state cost breakdowns, warns at 80% usage, and raises `BudgetExhaustedError` to cleanly stop the agent before overspending.

#### FILES TO MODIFY:

##### `agent/core/budget.py` (FULL IMPLEMENTATION — replace Phase 2 stub)
- **`BudgetReport` BaseModel:** total_tokens, total_cost_usd, max_tokens, max_cost_usd, token_percent, cost_percent, per_model_breakdown, per_state_breakdown, warning_threshold_hit
- **`BudgetExhaustedError(Exception)`:** stores `BudgetReport`
- **`Budget` class:**
  - `__init__(max_tokens: int = 100_000, max_cost_usd: float = 0.50)`:
    - Store limits
    - `self._total_tokens: int = 0`
    - `self._total_cost: float = 0.0`
    - `self._per_model: dict[str, dict] = {}`
    - `self._per_state: dict[str, dict] = {}`
    - `self._warning_issued: bool = False`
  - `record(input_tokens: int, output_tokens: int, model: str, state: str = "", cost: float | None = None)`:
    - Add tokens to total
    - If `cost` provided: use it. Else: calculate via `litellm.completion_cost()` or per-model pricing from `config/models.yaml`
    - Update `self._per_model[model]` and `self._per_state[state]`
    - If > 80% and not yet warned: log warning "⚠️ 80% of budget used"
  - `can_continue() -> bool`:
    - `return self._total_tokens < self.max_tokens and self._total_cost < self.max_cost`
  - `check_or_raise()`:
    - If not `can_continue()`: raise `BudgetExhaustedError(self.report())`
  - `report() -> BudgetReport`:
    - Compute all percentages and breakdowns
    - Return `BudgetReport`
  - `format_report() -> str`:
    - Format: "Tokens: 45,230/100,000 (45%) | Cost: $0.12/$0.50 (24%) | Remaining: 54,770 tokens, $0.38"
  - `reset()`:
    - Zero all counters
  - `get_breakdown() -> dict`:
    - Return per-model and per-state breakdown

##### `tests/test_budget.py`
- `test_record_accumulates_tokens`: Record 3 calls, verify total
- `test_record_accumulates_cost`: Record calls with cost, verify total
- `test_can_continue_under_budget`: Verify True when under limits
- `test_can_continue_over_tokens`: Verify False when tokens exceeded
- `test_can_continue_over_cost`: Verify False when cost exceeded
- `test_check_or_raise_raises`: Verify BudgetExhaustedError raised
- `test_warning_at_80_percent`: Record to 81%, verify warning (check log)
- `test_per_model_breakdown`: Record for 2 models, verify breakdown
- `test_per_state_breakdown`: Record for 2 states, verify breakdown
- `test_format_report_includes_all`: Verify formatted string includes tokens, cost, percentages
- `test_reset_zeros_all`: Reset, verify everything zeroed

#### ACCEPTANCE CRITERIA:

- [ ] Token and cost tracking accumulates correctly
- [ ] `check_or_raise()` raises `BudgetExhaustedError` when exceeded
- [ ] Warning is issued at 80% usage (only once)
- [ ] Per-model and per-state breakdowns are tracked
- [ ] `format_report()` produces human-readable output
- [ ] Budget check happens BEFORE LLM calls (not after)
- [ ] All 11 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_budget.py -v` — all pass
2. Test budget enforcement: `uv run agent run "task" --max-cost 0.01` — should stop quickly with budget message

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT check budget AFTER making an LLM call. Check BEFORE. Prevents the last call from going over budget.
- Do NOT forget to include retry costs. A rate-limited call that retries 3 times costs 3×.
- Do NOT issue the 80% warning more than once per task. Track `_warning_issued`.

---

### PHASE 3.8 — MCP (MODEL CONTEXT PROTOCOL) SUPPORT

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.5 (ToolRegistry)
**ESTIMATED DURATION:** 2.5 hours
**GOAL:** An `MCPRegistry` that connects to external MCP servers via JSON-RPC 2.0 over stdio, discovers their tools, and registers them in the ToolRegistry with server-name prefixes.

#### FILES TO CREATE:

##### `agent/tools/mcp.py`
- **`MCPServerConfig` BaseModel:** name, command, args, env
- **`MCPToolDefinition` BaseModel:** server_name, tool_name, qualified_name, description, parameters
- **`MCPRegistry` class:**
  - `__init__(tool_registry: ToolRegistry)`:
    - Store registry reference
    - `self._servers: dict[str, subprocess.Popen] = {}`
    - `self._tools: dict[str, MCPToolDefinition] = {}`
  - `async connect(config: MCPServerConfig)`:
    - Launch subprocess: `subprocess.Popen([config.command] + config.args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env={**os.environ, **config.env})`
    - Send JSON-RPC 2.0 `initialize` request
    - Call `tools/list` to discover available tools
    - For each tool:
      - Create `MCPToolDefinition` with `qualified_name = f"{config.name}.{tool.name}"`
      - Register in ToolRegistry with BUILD-only permissions
    - Store process in `self._servers[config.name]`
  - `async call_tool(qualified_name: str, params: dict) -> dict`:
    - Parse server_name from qualified_name
    - Send JSON-RPC 2.0 `tools/call` request to correct server process
    - Read response from stdout
    - Parse JSON-RPC response, return result
  - `async disconnect(server_name: str)`:
    - Terminate subprocess
    - Remove from `self._servers`
    - Remove tools from registry
  - `async disconnect_all()`:
    - Disconnect all servers
    - Called on agent shutdown
  - `_send_jsonrpc(process: Popen, method: str, params: dict) -> dict`:
    - Build JSON-RPC 2.0 request: `{"jsonrpc": "2.0", "id": uuid, "method": method, "params": params}`
    - Write to process stdin
    - Read response from stdout
    - Parse and return result
- **Edge cases:**
  - MCP server fails to start: log warning, skip, continue with built-in tools
  - MCP server crashes mid-session: detect broken pipe, attempt 1 reconnect, then disable
  - Tool name collisions: prefix with server name (e.g., `github.create_issue`)
  - Subprocess cleanup in `finally` block on agent shutdown

##### `tests/test_mcp.py`
- `test_connect_launches_subprocess`: Mock subprocess, verify launched
- `test_tool_discovery_registers_tools`: Mock tools/list response, verify tools registered
- `test_tool_naming_uses_prefix`: Verify qualified_name format: `server.tool`
- `test_call_tool_sends_jsonrpc`: Mock subprocess, verify JSON-RPC format
- `test_disconnect_terminates_process`: Connect then disconnect, verify terminated
- `test_disconnect_all_cleans_up`: Connect 2 servers, disconnect all, verify all terminated
- `test_failed_server_skipped`: Mock failed launch, verify warning logged, no crash
- `test_build_only_permissions`: Verify MCP tools have BUILD-only permissions

#### FILES TO MODIFY:

##### `config/default.yaml`
- Add MCP configuration section:
  ```yaml
  mcp_servers: []
  # Example:
  # - name: filesystem
  #   command: npx
  #   args: ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
  ```

#### ACCEPTANCE CRITERIA:

- [ ] MCP servers launch as subprocesses
- [ ] Tool discovery via `tools/list` works
- [ ] Tools are registered with `server.tool` naming convention
- [ ] `call_tool()` sends proper JSON-RPC 2.0 requests
- [ ] Failed servers are skipped gracefully (no crash)
- [ ] All processes are cleaned up on disconnect
- [ ] MCP tools have BUILD-only permissions
- [ ] All 8 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_mcp.py -v` — all pass
2. (Optional) Configure a filesystem MCP server, verify tool registration
3. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT forget to prefix MCP tool names with the server name. Name collisions with built-in tools cause silent overwrites.
- Do NOT leave subprocess pipes open. Always cleanup in `finally`.
- Do NOT block the event loop with synchronous subprocess I/O. Use `asyncio.subprocess` or run in executor.
- Do NOT grant MCP tools PLAN or REVIEW permissions. They are BUILD-only by default.

---

### PHASE 3.9 — GIT INTEGRATION

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.1 (gitpython dependency)
**ESTIMATED DURATION:** 2 hours
**GOAL:** A `GitManager` that stashes user changes, auto-commits agent work with structured messages, and provides diffs — keeping the git history clean and the user's work safe.

#### FILES TO CREATE:

##### `agent/tools/git_tools.py`
- **`CommitInfo` BaseModel:** sha, message, files_changed, task_id, timestamp
- **`GitManager` class:**
  - `__init__(project_dir: str)`:
    - Try: `self.repo = git.Repo(project_dir)`
    - Catch `git.InvalidGitRepositoryError`: set `self._available = False`, log warning
  - `stash_user_changes() -> bool`:
    - If `self._available == False`: return False
    - If working tree is dirty: `self.repo.git.stash("push", "-m", f"agent-stash-{timestamp}")`
    - Return True if stashed, False if clean
  - `unstash() -> bool`:
    - If no stash: return False
    - Try: `self.repo.git.stash("pop")`
    - Catch merge conflict: log warning "Merge conflict on unstash — manual resolution needed", return False
    - Return True
  - `auto_commit(task_id: str, summary: str, files: list[str], metrics: dict) -> CommitInfo | None`:
    - If `self._available == False`: return None
    - `git add` only the specified files (NEVER `git add -a`)
    - Build commit message:
      ```
      [agent] task:{task_id} status:success

      Summary: {summary}
      Files changed: {', '.join(files)}
      Iterations: {metrics['iterations']}
      Tokens used: {metrics['tokens']:,}
      Cost: ${metrics['cost']:.4f}
      ```
    - Commit: `self.repo.index.commit(message)`
    - Return `CommitInfo`
  - `get_diff(files: list[str] | None = None) -> str`:
    - If files: `self.repo.git.diff("--", *files)`
    - Else: `self.repo.git.diff()`
    - Return unified diff string
  - `is_dirty() -> bool`:
    - Return `self.repo.is_dirty(untracked_files=True)`
- **Edge cases:**
  - Not a git repo: all operations become no-ops, no crash
  - Detached HEAD: commit still works, warn about branch state
  - Merge conflicts on stash pop: warn user, do NOT auto-resolve

##### `tests/test_git.py`
- `test_stash_user_changes_when_dirty`: Create dirty repo, stash, verify clean
- `test_stash_returns_false_when_clean`: Clean repo, verify False
- `test_unstash_restores_changes`: Stash and unstash, verify restored
- `test_auto_commit_adds_specific_files`: Create files, commit, verify only specified files committed
- `test_auto_commit_never_uses_add_all`: Verify `git add -a` is NEVER used
- `test_commit_message_format`: Verify structured commit message
- `test_get_diff_shows_changes`: Modify file, verify diff output
- `test_not_a_git_repo_no_crash`: Run on non-git directory, verify no crash
- `test_is_dirty_detects_changes`: Create untracked file, verify dirty

#### ACCEPTANCE CRITERIA:

- [ ] User changes are stashed before agent work
- [ ] Agent commits only specific files (never `git add -a`)
- [ ] Commit messages include task_id, summary, files, metrics
- [ ] `unstash()` restores user changes after agent completes
- [ ] Not-a-git-repo is handled gracefully (no crash)
- [ ] All 9 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_git.py -v` — all pass
2. Create a git repo, make uncommitted changes, run agent, verify changes stashed/unstashed
3. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT use `git add -a` or `git commit -a`. This will commit the user's uncommitted changes. Always `git add <specific_files>`.
- Do NOT auto-resolve merge conflicts. Warn the user and let them resolve manually.
- Do NOT crash if not in a git repo. All operations must be no-ops in that case.

---

### PHASE 3.10 — EVALUATION HARNESS

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.9 (Harness — the agent must be runnable)
**ESTIMATED DURATION:** 3 hours
**GOAL:** An evaluation harness with 20 curated tasks (easy/medium/hard) that benchmarks the agent's solve rate, cost, and iteration count — producing measurable results for the README.

#### FILES TO CREATE:

##### `eval/harness.py`
- **`EvalTask` BaseModel:** id, difficulty, description, test_file, expected_files, max_iterations, timeout_seconds
- **`EvalResult` BaseModel:** task_id, solved, iterations, tokens, cost_usd, duration_seconds, error
- **`EvalReport` BaseModel:** results, solve_rate, avg_iterations, avg_cost, avg_time, per_difficulty, timestamp
- **`EvaluationHarness` class:**
  - `__init__(agent_harness: AgentHarness)`:
    - Store reference
  - `async run(tasks: list[EvalTask] | None = None) -> EvalReport`:
    - If tasks is None: load all from `eval/tasks/`
    - For each task:
      - Create fresh temp directory
      - Copy test file into directory
      - Run agent with task description as goal, with `max_iterations` and `timeout`
      - Record `EvalResult`: solved, iterations, tokens, cost, time, error
    - Aggregate into `EvalReport`:
      - `solve_rate`: percentage of tasks solved
      - `avg_iterations`, `avg_cost`, `avg_time`: averages
      - `per_difficulty`: breakdown by easy/medium/hard
    - Save results to `eval/results/{timestamp}.json`
    - Return `EvalReport`
  - `compare(current: EvalReport, previous: EvalReport) -> str`:
    - Show improvement/regression for each metric
    - Format as Rich table with green (improved) / red (regressed) colors
    - Return formatted string
  - `_load_tasks(task_dir: str = "eval/tasks") -> list[EvalTask]`:
    - Read all `.yaml` files in task_dir
    - Parse into `EvalTask` objects
    - Return sorted by difficulty (easy first)

##### `eval/tasks/` — Create 20 YAML task files:

**Easy (7 tasks):**
- `reverse_string.yaml`: Write a function that reverses a string
- `add_numbers.yaml`: Write a function that adds two numbers
- `fibonacci.yaml`: Write a function that returns the nth Fibonacci number
- `palindrome.yaml`: Write a function that checks if a string is a palindrome
- `factorial.yaml`: Write a function that computes factorial
- `count_vowels.yaml`: Write a function that counts vowels in a string
- `max_in_list.yaml`: Write a function that finds the maximum in a list

**Medium (7 tasks):**
- `stack_class.yaml`: Write a Stack class with push/pop/peek/is_empty
- `linked_list.yaml`: Write a singly linked list with insert/delete/search
- `binary_search.yaml`: Write binary search with edge case handling
- `matrix_multiply.yaml`: Write matrix multiplication
- `json_parser.yaml`: Write a simple JSON key-value parser
- `rate_limiter.yaml`: Write a token bucket rate limiter
- `lru_cache.yaml`: Write an LRU cache with O(1) operations

**Hard (6 tasks):**
- `rest_api.yaml`: Write a REST API with CRUD endpoints (using Flask)
- `async_task_queue.yaml`: Write an async task queue with priority
- `expression_evaluator.yaml`: Write a math expression evaluator (operator precedence)
- `file_watcher.yaml`: Write a file watcher that detects changes
- `cli_todo_app.yaml`: Write a CLI todo app with persistence
- `graph_shortest_path.yaml`: Write Dijkstra's shortest path algorithm

Each YAML file follows this format:
```yaml
id: reverse_string
difficulty: easy
description: "Write a Python function called 'reverse_string' that takes a string and returns it reversed. Write comprehensive pytest tests."
test_file: |
  def test_reverse_string():
      from solution import reverse_string
      assert reverse_string("hello") == "olleh"
      assert reverse_string("") == ""
      assert reverse_string("a") == "a"
      assert reverse_string("racecar") == "racecar"
expected_files: [solution.py]
max_iterations: 5
timeout_seconds: 300
```

##### `tests/test_eval_harness.py`
- `test_load_tasks_from_yaml`: Verify all 20 tasks load correctly
- `test_eval_result_structure`: Verify EvalResult fields
- `test_eval_report_aggregation`: Create 5 results, verify aggregation math
- `test_compare_reports`: Create 2 reports, verify comparison output
- `test_results_saved_to_json`: Run eval (mocked), verify JSON saved
- `test_per_difficulty_breakdown`: Verify easy/medium/hard breakdown correct

#### ACCEPTANCE CRITERIA:

- [ ] 20 eval tasks load correctly from YAML files
- [ ] Evaluation runs each task in isolation (fresh temp directory)
- [ ] Results are aggregated correctly (solve_rate, averages, per-difficulty)
- [ ] Results are saved to `eval/results/{timestamp}.json` (version-tracked)
- [ ] `compare()` shows improvement/regression between runs
- [ ] All 6 test cases pass
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_eval_harness.py -v` — all pass
2. (Optional, costs money) Run `uv run agent eval --tasks eval/tasks/reverse_string.yaml` — verify single task evaluation
3. Run full suite: `uv run pytest tests/ -v`

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT run eval tasks in the actual project workspace. Always create a fresh temp directory.
- Do NOT forget to set timeouts. A hanging eval task blocks the entire evaluation run.
- Do NOT hardcode expected outputs in eval tasks. Test files define correctness — the agent just needs to make them pass.

---

### PHASE 3.11 — TRAJECTORY LOGGING ENHANCEMENTS

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.10 (TrajectoryLogger)
**ESTIMATED DURATION:** 1.5 hours
**GOAL:** Add `replay` (interactive step-through) and `export` (Markdown report) commands to the trajectory logger for debugging and demos.

#### FILES TO MODIFY:

##### `agent/core/trajectory.py`
- **Add `replay(task_id: str)` method:**
  - Read JSONL file for the task
  - For each step:
    - Display with Rich formatting: state badge, agent name, action description, tool calls, result
    - Color-code: green (success), red (failure), yellow (partial)
    - Pause between steps (user presses Enter to continue, or `q` to quit)
  - Useful for debugging and portfolio demos
- **Add `export(task_id: str, format: str = "markdown") -> str` method:**
  - Read JSONL trajectory
  - Convert to readable Markdown document:
    - Title: "Trajectory: {task_id}"
    - For each step: heading with state, agent, action, code diffs, test results
    - Summary: total steps, tokens, cost, duration, final result
  - Return Markdown string (also save to file)

##### `ui/cli.py`
- Add `replay` command: `uv run agent replay <task_id>` — interactive step-through
- Add `export` command: `uv run agent export <task_id>` — export to Markdown

#### ACCEPTANCE CRITERIA:

- [ ] `replay()` displays each step interactively with Rich formatting
- [ ] `export()` generates a readable Markdown document
- [ ] CLI commands `agent replay` and `agent export` work
- [ ] All Phase 1+2 tests still pass

#### MANUAL TEST STEPS:

1. Run a task, then `uv run agent replay <task_id>` — verify interactive display
2. Run `uv run agent export <task_id>` — verify Markdown output

---

### PHASE 3.12 — ERROR BOUNDARIES AND LOADING STATES

**STATUS:** NOT STARTED
**DEPENDS ON:** All previous phases
**ESTIMATED DURATION:** 2 hours
**GOAL:** Comprehensive error handling across all modules and Rich-formatted loading states in the CLI — making the agent robust and polished.

#### FILES TO MODIFY:

##### All modules — add error classification:
- **Recoverable:** LLM rate limit → retry with backoff (already done in Phase 1.2)
- **Degraded:** ChromaDB unavailable → disable vector search, continue with FTS5 only
- **Fatal:** Docker daemon unavailable → display clear error message, suggest fix, exit

##### `ui/display.py` — add loading states:
- Model loading: Rich spinner with "Loading model configuration..."
- Docker check: spinner with "Verifying Docker availability..."
- Memory loading: spinner with "Loading memory from previous sessions..."
- Repo map building: spinner with "Building codebase structure map..."
- Memory maintenance: spinner with "Running /dream memory maintenance..."

##### `ui/cli.py` — add graceful degradation:
- On import error (missing optional dependency): show clear message about what's missing and how to install
- On config error: show which field is wrong and what the expected format is

#### ACCEPTANCE CRITERIA:

- [ ] Every external call is wrapped in appropriate error handling
- [ ] Recoverable/degraded/fatal errors are classified correctly
- [ ] Loading spinners display during initialization
- [ ] Missing optional dependencies show clear install instructions
- [ ] No stack traces shown to the user (only formatted error panels)
- [ ] All Phase 1+2 tests still pass

---

### PHASE 3.13 — README GENERATION

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 3.10 (Evaluation results for the README)
**ESTIMATED DURATION:** 2 hours
**GOAL:** A complete, portfolio-ready README.md with architecture diagram, features, quick start, evaluation results, and comparison table.

#### FILES TO CREATE:

##### `README.md` (FULL REWRITE)
Sections:
1. **Title + badge + one-line description:** "Self-Improving Coding Agent — An autonomous agent that learns from its mistakes"
2. **Architecture diagram:** Mermaid diagram of the system:
   - FSM states and transitions
   - Agent pipeline: Architect → Worker → Judge
   - Memory layers: Working → Session → FTS5 → ChromaDB
   - Tool registry with 7 tools + MCP
3. **Key Features:** bullet list:
   - 8-state FSM orchestration
   - Architect/Worker/Judge multi-agent pipeline
   - 4-layer memory (working, session, indexed, vector)
   - 3-level hierarchical fault localization
   - Multi-candidate fix search (N=3)
   - Self-improvement via `/dream` and `/distill`
   - Triple-condition circuit breaker
   - Docker sandboxed execution
   - Context compaction at 60% utilization
   - BYOK model support via LiteLLM
4. **Quick Start:** `git clone`, `uv sync`, set API key, `uv run agent run "your goal"`
5. **How It Works:** brief explanation of the Plan → Code → Analyze → Test → Reflect loop
6. **Evaluation Results:** table from eval harness (solve rate, cost, iterations by difficulty)
7. **Comparison Table:** Your agent vs. Devin vs. Claude Code vs. SWE-Agent (features, not benchmarks)
8. **Configuration:** how to configure models, budgets, permissions, MCP servers
9. **Architecture Deep Dive:** expanded explanation of each component
10. **Contributing:** how to add eval tasks, tools, memory backends
11. **License:** MIT

#### ACCEPTANCE CRITERIA:

- [ ] README has all 11 sections
- [ ] Mermaid architecture diagram renders correctly
- [ ] Quick start instructions are accurate and work on a fresh clone
- [ ] Evaluation results table is populated (even if placeholder values initially)

---

### PHASE 3.14 — SANDBOX HARDENING

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.4 (DockerSandbox)
**ESTIMATED DURATION:** 1 hour
**GOAL:** Harden the Docker sandbox with non-root user execution, proper image building, and auto-build on first use.

#### FILES TO MODIFY:

##### `docker/Dockerfile.sandbox`
- Add non-root user:
  ```dockerfile
  FROM python:3.11-slim
  RUN pip install --no-cache-dir pytest pytest-json-report ruff mypy bandit
  RUN useradd -m agent
  USER agent
  WORKDIR /workspace
  ```
- Build tag: `agent-sandbox`

##### `agent/tools/sandbox.py`
- Add auto-build: if `agent-sandbox` image not found, build from `docker/Dockerfile.sandbox`
- Use `agent-sandbox` image by default instead of `python:3.11-slim`
- If build fails (network issues): fall back to `python:3.11-slim` with runtime tool installation

#### ACCEPTANCE CRITERIA:

- [ ] Sandbox runs as non-root user inside container
- [ ] Custom image auto-builds on first use
- [ ] Fallback to base image if custom build fails
- [ ] All existing sandbox tests pass

---

### PHASE 3.15 — FINAL E2E INTEGRATION TESTING AND POLISH

**STATUS:** NOT STARTED
**DEPENDS ON:** ALL previous Phase 3 phases (3.1–3.14)
**ESTIMATED DURATION:** 3 hours
**GOAL:** Full end-to-end integration tests verifying the complete agent pipeline, with all Phase 3 components wired together.

#### FILES TO CREATE:

##### `tests/test_e2e.py`
- **Test 1 — Greenfield task:**
  - Goal: "Write a function that checks if a number is prime + write tests"
  - Assert: agent creates solution.py and test file, tests pass, cost < $0.50
- **Test 2 — Bug-fix task:**
  - Provide a buggy file + failing tests
  - Goal: "Fix the failing tests"
  - Assert: agent identifies bug, fixes it, tests pass, iterations < 5
- **Test 3 — Memory persistence:**
  - Run task A (success), then task B (similar error to A)
  - Assert: task B retrieves task A's failure record from ChromaDB, solves faster
- **Test 4 — Circuit breaker:**
  - Provide impossible task
  - Assert: agent stops after max_iterations, reports failure with trip reason
- **Test 5 — Checkpoint resume:**
  - Start task, kill at iteration 3, restart
  - Assert: agent resumes from iteration 3, not from scratch
- Use mock LLM for deterministic testing (record/replay actual LLM responses)

#### FILES TO MODIFY:

##### `ui/cli.py`
- Wire all Phase 3 components:
  - Add `dream` command: `uv run agent dream` — run `/dream` maintenance
  - Add `distill` command: `uv run agent distill` — run `/distill` skill extraction
  - Add `eval` command: `uv run agent eval` — run evaluation harness
  - Add `replay` command: `uv run agent replay <task_id>` — replay trajectory
  - Add `export` command: `uv run agent export <task_id>` — export trajectory
  - Add `memory search` command: `uv run agent memory search "query"` — search FTS5

##### All `__init__.py` files
- Ensure all Phase 3 components are properly exported

#### ACCEPTANCE CRITERIA (COMPREHENSIVE — ALL PHASE 3 CRITERIA):

- [ ] Architect generates valid DAG for multi-file task
- [ ] Judge rejects obviously bad code (test with intentionally buggy output)
- [ ] Context compaction triggers at 60% and preserves file paths/errors
- [ ] Multi-candidate search finds better fix than single-candidate on at least 1 eval task
- [ ] `/dream` deduplicates, validates paths, compresses logs, prunes failures
- [ ] `/distill` extracts a skill from 3+ similar successful tasks
- [ ] Cost budget prevents overspending (test with `max_cost: 0.01`)
- [ ] MCP server registration works with at least 1 external server
- [ ] Git auto-commit creates properly formatted commits
- [ ] Eval harness produces results table with solve_rate/cost/iterations breakdown
- [ ] README contains architecture diagram, eval results, comparison table
- [ ] All 5 E2E tests pass
- [ ] `ruff check agent/ providers/ ui/ eval/ --select ALL` returns 0 errors
- [ ] `mypy agent/ providers/ ui/ eval/ --strict` returns 0 errors
- [ ] No orphaned Docker containers after any run
- [ ] All Phase 1+2+3 unit tests pass: `uv run pytest tests/ -v`

#### MANUAL TEST STEPS:

1. Run full test suite: `uv run pytest tests/ -v --tb=short` — all green
2. Run linters: `uv run ruff check .` and `uv run mypy agent/ providers/ ui/ eval/ --strict`
3. Run a full task: `uv run agent run "Write a REST API endpoint"` — verify Architect/Worker/Judge cycle
4. Run eval: `uv run agent eval --tasks eval/tasks/reverse_string.yaml` — verify results
5. Run dream: `uv run agent dream` — verify report
6. Test budget: `uv run agent run "task" --max-cost 0.01` — verify budget stop
7. Verify Docker cleanup: `docker ps -a --filter label=agent.sandbox=true` — should be empty
8. Verify README renders correctly on GitHub

---

## 7 — ENVIRONMENT VARIABLES MASTER LIST

| Variable Name | Required/Optional | Where Used | Where To Get It | Example Value |
|---------------|-------------------|-----------|-----------------|---------------|
| `GEMINI_API_KEY` | **Required** | `providers/llm.py` | [Google AI Studio](https://aistudio.google.com/apikey) | `AIzaSyB...xyz` |
| `OPENAI_API_KEY` | Optional (BYOK) | `providers/llm.py` via LiteLLM | [OpenAI Platform](https://platform.openai.com/api-keys) | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Optional (BYOK) | `providers/llm.py` via LiteLLM | [Anthropic Console](https://console.anthropic.com/) | `sk-ant-...` |
| `DEFAULT_STRONG_MODEL` | Optional | `providers/llm.py` | Set by user | `gemini/gemini-2.5-flash` |
| `DEFAULT_FAST_MODEL` | Optional | `providers/llm.py` | Set by user | `gemini/gemini-2.0-flash` |
| `DOCKER_ENABLED` | Optional (default: `true`) | `agent/tools/sandbox.py` | Set by user | `true` or `false` |
| `LOG_LEVEL` | Optional (default: `INFO`) | All modules | Set by user | `DEBUG`, `INFO`, `WARNING` |
| `AGENT_MODEL_PLANNING` | Optional (override) | `providers/llm.py` | Set by user | `openai/gpt-4o` |
| `AGENT_MODEL_CODING` | Optional (override) | `providers/llm.py` | Set by user | `anthropic/claude-3-5-sonnet` |
| `AGENT_MODEL_REFLECTION` | Optional (override) | `providers/llm.py` | Set by user | `gemini/gemini-2.5-flash` |
| `AGENT_MODEL_JUDGE_REVIEW` | Optional (override) | `providers/llm.py` | Set by user | `gemini/gemini-2.5-flash` |
| `GITHUB_TOKEN` | Optional (for MCP) | `agent/tools/mcp.py` | [GitHub Settings](https://github.com/settings/tokens) | `ghp_...` |
| `NO_COLOR` | Optional | `ui/display.py` | Set by user | `1` |

---

## 8 — TESTING STRATEGY

### Unit Tests

| Phase | Test File | Framework | Minimum Test Cases |
|-------|-----------|-----------|-------------------|
| 3.1 | `tests/test_architect.py` | pytest + pytest-asyncio | 5 cases: plan, dependencies, cyclic retry, replan, single-task |
| 3.1 | `tests/test_judge.py` | pytest + pytest-asyncio | 4 cases: approve, reject, confidence, issues |
| 3.1 | `tests/test_worker.py` | pytest + pytest-asyncio | 4 cases: execute, code_result, fix_lint, revise |
| 3.2 | `tests/test_architect.py` (additions) | pytest | 11 cases: DAG validation, ready tasks, downstream, replan branch |
| 3.3 | `tests/test_context_manager.py` | pytest + pytest-asyncio | 9 cases: layer order, compaction trigger, preservation, token estimation |
| 3.4 | `tests/test_fix_searcher.py` | pytest + pytest-asyncio | 7 cases: best candidate, all fail, temperature, lint filter, ranking |
| 3.5 | `tests/test_dream.py` | pytest + pytest-asyncio | 11 cases: scan, deduplicate, validate, compress, prune, reindex, report |
| 3.6 | `tests/test_distill.py` | pytest + pytest-asyncio | 8 cases: pattern detection, LCS, templatize, validate, insufficient data |
| 3.7 | `tests/test_budget.py` | pytest | 11 cases: accumulation, limits, warning, breakdowns, format, reset |
| 3.8 | `tests/test_mcp.py` | pytest | 8 cases: connect, discovery, naming, call, disconnect, failure handling |
| 3.9 | `tests/test_git.py` | pytest | 9 cases: stash, unstash, auto_commit, diff, not-a-repo |
| 3.10 | `tests/test_eval_harness.py` | pytest | 6 cases: load tasks, result structure, aggregation, comparison |

### Integration Tests

| Phase | What To Test | Tool |
|-------|-------------|------|
| 3.15 | Greenfield task end-to-end | Mock LLM E2E test |
| 3.15 | Bug-fix task end-to-end | Mock LLM E2E test |
| 3.15 | Memory persistence across tasks | Mock LLM E2E test |
| 3.15 | Circuit breaker enforcement | Mock LLM E2E test |
| 3.15 | Checkpoint resume | Mock LLM E2E test |

### Test Totals

| Phase | New Tests |
|-------|-----------|
| Phase 1 | ~58 tests |
| Phase 2 | ~106 tests |
| Phase 3 | ~93 tests + 5 E2E |
| **Total** | **~262 tests** |

---

## 9 — DEPLOYMENT CHECKLIST

Phase 3 completes the agent. This is the final deployment checklist.

1. **Verify Phase 1 + 2 fully working:** `uv run pytest tests/ -v` — all green
2. **Install new dependencies:** `uv sync` (picks up tiktoken, etc.)
3. **Build hardened sandbox:** `docker build -t agent-sandbox docker/`
4. **Run full test suite:** `uv run pytest tests/ -v` — all green
5. **Run linters:** `uv run ruff check .` and `uv run mypy agent/ providers/ ui/ eval/ --strict`
6. **Run evaluation:** `uv run agent eval` — generate baseline results
7. **Verify all CLI commands:**
   - `uv run agent run "Write a hello world function"` ✓
   - `uv run agent config` ✓
   - `uv run agent version` ✓
   - `uv run agent dream` ✓
   - `uv run agent distill` ✓
   - `uv run agent eval` ✓
   - `uv run agent replay <task_id>` ✓
   - `uv run agent export <task_id>` ✓
   - `uv run agent memory search "query"` ✓
8. **Verify README renders correctly:** Push to GitHub, check rendering
9. **Git cleanup:** `git tag v1.0.0`, push tags
10. **Docker cleanup:** `docker ps -a --filter label=agent.sandbox=true` — empty
11. **Final commit:** `feat: v1.0.0 — complete self-improving coding agent`

---

## 10 — INITIAL TRACKER SETUP

Update the existing `tracker.md` by appending Phase 3 rows to the Phase Status Tracker. Do NOT replace Phase 1 or Phase 2 rows.

### Additional `tracker.md` Rows:

```markdown
| 3.1 | Architect/Worker/Judge | NOT STARTED | — | — | Multi-agent pipeline with typed messages |
| 3.2 | DAG Task Planning | NOT STARTED | — | — | Topological sort, cycle detection, replan |
| 3.3 | Context Compaction | NOT STARTED | — | — | 6-layer context, compact at 60% |
| 3.4 | Multi-Candidate Fix | NOT STARTED | — | — | N=3 candidates, temperature=0.7 |
| 3.5 | /dream Maintenance | NOT STARTED | — | — | 7-step: dedup, validate, compress, prune, reindex |
| 3.6 | /distill Skills | NOT STARTED | — | — | Pattern detection, LCS, templatize |
| 3.7 | Budget System | NOT STARTED | — | — | Per-model/state tracking, 80% warning |
| 3.8 | MCP Support | NOT STARTED | — | — | JSON-RPC 2.0 over stdio |
| 3.9 | Git Integration | NOT STARTED | — | — | Stash, auto-commit, diff |
| 3.10 | Eval Harness | NOT STARTED | — | — | 20 tasks, solve rate, comparison |
| 3.11 | Trajectory Enhancements | NOT STARTED | — | — | replay + export commands |
| 3.12 | Error Boundaries | NOT STARTED | — | — | Recoverable/degraded/fatal + loading states |
| 3.13 | README Generation | NOT STARTED | — | — | Full portfolio README with Mermaid diagram |
| 3.14 | Sandbox Hardening | NOT STARTED | — | — | Non-root user, auto-build |
| 3.15 | Final E2E Testing | NOT STARTED | — | — | 5 integration tests, full wiring |
```

### Rules for `tracker.md` (unchanged from Phase 1):

1. Update the Phase Status Tracker after completing each phase. Valid statuses: `NOT STARTED`, `IN PROGRESS`, `DONE`, `BLOCKED`.
2. Log every blocker immediately when encountered.
3. Log every deviation from this plan.
4. `tracker.md` is the ONLY file you modify for project management.
5. At the end of every coding session, update `tracker.md` with current progress before stopping.
