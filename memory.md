# Long-Term Project Memory

This file serves as the permanent memory for the Self-Improving Coding Agent (SICA). It tracks completed phases, architectural decisions, deviations from the original plan, and critical lessons learned.

---

## Phase 1: Foundation (COMPLETED)

### What Was Built
- **1.1 Scaffolding:** Configured the project with `uv` as the package manager. Set up strict linting (`ruff`), strict typing (`mypy --strict`), and `pytest` for testing.
- **1.2 LLM Abstraction:** Built `LLMProvider` over `litellm` in `providers/llm.py`, allowing dynamic model switching via `config/models.yaml`.
- **1.3 Finite State Machine:** Implemented an 8-state FSM (`IDLE`, `LOCALIZING`, `PLANNING`, `CODING`, `TESTING`, `REFLECTING`, `COMPLETED`, `FAILED`) in `agent/core/state_machine.py` to dictate agent flow.
- **1.4 Execution Sandbox:** Built `DockerSandbox` using the `docker` Python SDK to run untrusted code in an ephemeral container.
- **1.5 Agent-Computer Interface (ACI):** Implemented a `ToolRegistry` that restricts available tools dynamically based on the active `AgentState` (e.g., you can't run tests while planning).
- **1.6 Circuit Breaker:** Added `CircuitBreaker` to forcefully halt execution if the agent enters an infinite loop or exceeds budget.
- **1.7 Working Memory:** Built `WorkingMemory` with string normalization logic to track previously tried hypotheses, effectively preventing the agent from retrying identical failed approaches.
- **1.8 CLI & UI:** Built the entrypoint using `Typer` (`ui/cli.py`) and a custom `Rich` status display (`ui/display.py`).
- **1.9 Orchestration Harness:** Wired all the above components together into a single execution loop inside `AgentHarness`.
- **1.10 Trajectory Logger:** Added JSONL logging to capture every state transition and tool execution for future observability.
- **1.11 Integration:** Passed all strict typing and linting checks, and successfully ran an end-to-end smoke test of the `agent run` CLI command.

### Deviations & Architectural Decisions
1. **No Custom Dockerfile:** The original Phase 1.4 plan suggested creating a custom `docker/Dockerfile`. We deviated from this and opted to pull the official `python:3.11-slim` image directly via the `docker-py` SDK. This reduced overhead and removed the need to build an image locally.
2. **Strict Typing Enforcement:** We committed to `mypy --strict` compliance from Day 1. This immediately proved its worth by catching a missing `await` on an async FSM transition in the Harness. We will maintain this standard.
3. **Early UI Refactor (DESIGN.md):** At the end of Phase 1, we introduced `DESIGN.md` (an opencode.ai dark theme design system). We immediately refactored the `Rich` terminal UI to use a custom theme mapping the specific hex codes from the design document. This clears the backlog and ensures all future terminal outputs built in Phase 2 will be perfectly styled.

### Important Lessons
- **Hypothesis Normalization is critical:** When tracking if an LLM is repeating itself, simple string matching fails because the LLM might change one word or whitespace. The string normalization step in `WorkingMemory` is crucial for detecting true loops.
- **Always `await` State Transitions:** Transitions in the FSM are asynchronous. Forgetting to await them causes silent failures or un-awaited coroutine warnings.

---

## Phase 2: Core Capabilities (COMPLETED)

### What Was Built
- **2.1 Session Memory:** Implemented `SessionMemory` to log facts, errors, patterns, and architecture into a human-readable `MEMORY.md` file, acting as a persistent long-term checkpoint.
- **2.2 Indexed Memory:** Implemented `IndexedMemory` using SQLite FTS5 for efficient full-text search across documentation and project files.
- **2.3 Failure Memory:** Implemented `FailureMemory` using ChromaDB for semantic vector-based search of past failed hypotheses, preventing repeated mistakes.
- **2.4 Reflection Engine:** Implemented an asynchronous 6-step reflection pipeline (`ReflectionEngine`) using the LLM for context-aware error classification and hypothesis generation.
- **2.5 Circuit Breaker Upgrades:** Expanded `CircuitBreaker` with comprehensive token limits, budget (USD) limits, and file-level error tracking using a new `BudgetTracker`.
- **2.6 Tree-Sitter Repo Map (Fallback):** Implemented a hierarchical `RepoMap` using Python's built-in `ast` module to extract classes, methods, and line numbers for context mapping.
- **2.7 Hierarchical Fault Localization:** Implemented `FaultLocalizer` which combines the Repo Map and LLM to pinpoint exact file paths and line ranges for bug fixes.
- **2.8 Harness Wiring & Checkpointing:** Integrated `SessionMemory` into `AgentHarness`, enabling automated task logging, persistent state checkpointing on interruption, and seamless resume capability.
- **2.9 Permission Modes:** Built `PermissionGate` with a strict `PERMISSION_MATRIX` restricting access to side-effect tools (like `edit_file`, `create_file`, `run_command`) based on the active mode (`PLAN`, `BUILD`, `REVIEW`). Integrated it seamlessly into the `ToolRegistry` and CLI.
- **2.10 Static Analysis Runner:** Implemented `StaticAnalyzer` to proactively lint, type-check, and vulnerability-scan the agent's code inside the Docker Sandbox using `ruff`, `mypy`, and `bandit`, returning structured `LintError` models.
- **2.11 Integration Smoke Test:** Activated all Phase 2 features by replacing the mocked transitions in `AgentHarness` with actual execution calls to `FaultLocalizer`, `StaticAnalyzer`, and `ReflectionEngine`. Successfully validated checkpoint recovery (`Ctrl+C` resumption) and end-to-end SQLite/ChromaDB logging.

### Deviations & Architectural Decisions
1. **Tree-Sitter Replaced by AST (Phase 2.6):** The planned `tree-sitter-languages` library failed to install correctly on Python 3.13 due to missing native binaries. We deviated from the original plan and successfully built a robust, zero-dependency fallback using Python's built-in `ast` module.
2. **Type Checking Overhaul for Dictionaries:** We explicitly typed dynamically populated dictionaries (`dict[str, Any]`) in `SessionMemory` rather than relying on inferred string types, strictly conforming to the `mypy --strict` mandate.
3. **Bypassing IDE Static Analysis Overreach:** When `mypy` strict mode conflicts with overly aggressive IDE static analysis (like Pyright on `docker-py` kwargs), dynamic typed unpacking (`**log_args: Any = {...}`) is a cleaner fallback than peppering the code with ignore tags.
4. **Testing Dependency Mocks (Phase 2.10):** Instead of introducing `pytest-mock` into the dependency tree for async static analysis testing, we natively used Python's `unittest.mock.AsyncMock` and `Mock`, keeping the testing dependencies minimal.

### Important Lessons
- **Timezone-Aware Datetimes:** Python 3.12+ formally deprecates `datetime.utcnow()`. This caused a cascade of warnings across the memory modules. The correct pattern is to replace all occurrences with timezone-aware `datetime.now(timezone.utc)`.
- **Cross-Platform File Locking Type Hints:** Using UNIX-specific libraries like `fcntl` on Windows causes strict IDE (Pyright) and MyPy errors. Using `# pyright: ignore` along with `# type: ignore` tags is essential to prevent CI/Lint pipelines from failing on OS-specific imports.
- **ResourceWarnings during Strict Testing:** Running pytest with `-W error` elevates all warnings to failures. We discovered that unclosed SQLite connections in background test fixtures can cascade into unrelated test failures. Strict testing requires extremely disciplined teardown logic.
- **Rich Theme Limitations:** The `rich` library's `Table` header styles will fail to parse composite custom theme styles (e.g., `"bold primary"`) if the theme maps `"primary"` to a hex code. Instead, define `"primary_bold": "bold #hex"` explicitly in the `Theme` dict.
- **Pydantic Validation on FSM Transitions:** When a Pydantic `BaseModel` defines required fields (like `iteration_count` in `StateSnapshot`), it is incredibly easy to miss passing them through abstract layers (like `**snapshot_kwargs` in `StateMachine.transition`). Explicitly tracing kwargs is vital.
- **Stub Mismatches in Integration:** When wiring together components built across different phases (like `LLMProvider` from Phase 1.2 and `AgentHarness` from Phase 1.9/2.8), it's crucial to verify method signatures (`complete` vs `generate`). Stubs written during early phases often drift from the final concrete implementations.
- **Circular Imports in Permissions:** Python module initialization order caused an `ImportError` when `agent.safety.permissions` imported `AgentMode` from `agent.tools.aci`, which in turn imported `PermissionGate`. Using `if TYPE_CHECKING:` in `aci.py` with forward references (e.g., `"PermissionGate | None"`) flawlessly breaks the circular loop.
- **Windows UTF-8 Encoding:** The `rich` CLI library threw a `UnicodeEncodeError` when trying to print an emoji (`🎯`) on Windows default `cp1252` charmap. Safely reconfiguring standard output via `sys.stdout.reconfigure(encoding="utf-8")` at the very start of the CLI entrypoint ensures universal terminal emoji support on Windows environments.
- **Docker-Py Log Demuxing:** The Python `docker` SDK's `logs()` method does not universally support the `demux=True` kwarg, throwing `unexpected keyword argument` exceptions on some versions/platforms. The safest approach is to omit `demux`, retrieve the mixed byte stream, and decode it into a single string for parsing.

---

## Phase 3: Deep Self-Improvement & Orchestration (COMPLETED)

### What Was Built
- **3.1 Architect Agent:** Built planning logic generating explicit DAGs representing dependencies between files.
- **3.2 Planner Enhancements:** Refined Architect to handle DAG cycles, validate downstream dependencies, and replan incrementally upon failures.
- **3.3 Worker Agent:** Built execution logic that consumes tasks from the Architect, uses the ToolRegistry to create/edit code, and automatically acts on test/lint failures natively.
- **3.4 Judge Agent:** Built independent review logic to objectively grade Worker completion without confirmation bias.
- **3.5 Context Compaction:** Implemented summarization routines in SessionMemory to prune and compact history once the token limit reaches 60% capacity.
- **3.6 Multi-Candidate Fix Search:** Upgraded ReflectionEngine/FaultLocalizer to generate and sandbox N=3 candidate fixes, scoring and choosing the one with the fewest lint errors and highest test pass rate.
- **3.7 Cost/Token Budget System:** Integrated a global `Budget` object to prevent LLM calls from overspending USD and tokens, with graceful halts at 100% capacity.
- **3.8 MCP Support:** Wired up an `MCPRegistry` to discover external server tools via JSON-RPC 2.0 over stdio, extending agent capabilities dynamically.
- **3.9 Git Integration:** Added a `GitManager` tool to automatically stash dirty working trees, commit changes selectively per task, and restore stashes without stepping on the user's workflow.
- **3.10 Evaluation Harness:** Created an automated benchmarking harness with 20 YAML-based tasks (Easy/Medium/Hard) to track the agent's solve rate and cost over time.
- **3.11 Trajectory Logging Enhancements:** Extended `TrajectoryLogger` with Rich-powered interactive `/replay` and `/export` to markdown functionality.
- **3.12 Error Boundaries & Loading States:** Added robust Rich spinners to UI and graceful fallbacks for missing components. Specifically implemented a global `try/except` block on CLI startup for missing optional dependencies (like `chromadb`), explicit Docker daemon unavailability warnings, and structured YAML syntax validation bounds during `config` parsing.
- **3.13 README Generation:** Wrote a comprehensive `README.md` featuring Mermaid architecture diagrams, evaluations, configuration options, and quick-start guides.
- **3.14 Sandbox Hardening:** Modified the DockerSandbox to use a non-root `agent` user via `Dockerfile.sandbox` and implemented internal auto-build logic for the image.
- **3.15 CLI Commands & E2E Testing:** Wired up new CLI commands (`dream`, `distill`, `eval`, `replay`, `export`, `search`) and achieved a 100% test pass rate across 208 unit and E2E tests, verified natively after the 3.12 integrations, with `ruff` and `mypy` strict compliance.

### Deviations & Architectural Decisions
1. **Eval Tasks Externalized:** Kept evaluation tasks as separate YAML files in `eval/tasks` rather than hardcoding them to allow easy external contributions.
2. **Auto-Build Sandbox in Python:** Avoided requiring the user to manually run `docker build` by handling the `ImageNotFound` exception inside `DockerSandbox` and invoking `client.images.build()` natively through Python.
3. **Safe Git Stashing:** Explicitly enforced the GitManager to `git add` precise files modified by the task and avoid `git add -a` to safeguard the user's concurrent, uncommitted work in the repository.

### Important Lessons
- **MCP Requires Strict Prefixing:** When mapping external MCP tools, name collisions with internal tools will silently overwrite functionality. Appending the server namespace prefix (`{server_name}.{tool_name}`) is critical.
- **Subprocess Hangs in MCP:** JSON-RPC over `stdio` easily leads to deadlocks if the pipes aren't flushed properly or if the async reading tasks are orphaned.
- **Token Tracking is Easy to Lose:** Passing token usage up the call stack through nested FSM layers is complex. The global `Budget` class instance passed into the provider offers a much more resilient tracking mechanism than bubbling up manual integers.
- **Static Analysis Slip-ups:** Moving rapidly through complex orchestrations (like Phase 3) can easily lead to neglected static typing (e.g., unannotated `list[str] = []`, implicit optionals) and disconnected CLI stubs (`dream()`/`distill()`). Strict static typing (`mypy --strict`) and IDE language servers (Pyright/Pylance) must be rigorously verified before calling a phase complete, even if unit tests pass, because IDEs will flag these issues immediately. This includes tracking down hidden async/await mismatches and integer casting on dynamic dictionaries.
- **Pyright CLI vs VS Code Pylance:** Pylance (VS Code's language server) uses a slightly different ruleset than the standard `pyright` CLI. While `pyright .` may report 0 errors, Pylance will still flag forward references (e.g., `PermissionGate | None`) if `from __future__ import annotations` is missing. Additionally, Pylance sometimes ignores `pyright: ignore` directives on missing optional imports (`git`, `docker`, `litellm`) and prefers the standard `# type: ignore`. Finally, Pylance employs extremely strict signature overloads for `os.path.join` (resolving to `ntpath.join` on Windows) which fails if it infers `Unknown | None` instead of a guaranteed `str` or `PathLike`. Always verify clean state against the IDE directly. However, be careful not to overcorrect: casting natively-typed `str` variables with `str()` will trigger unnecessary type conversion warnings.
- **Unknown Type Narrowing Failure:** When a module is imported with `# type: ignore` (e.g., `import git`), Pylance treats all types from that module as `Unknown`. Even after a `if not self.repo:` guard, Pylance cannot narrow `Unknown | None` to just `Unknown`. The fix is to explicitly annotate the attribute as `Any` (e.g., `self.repo: Any = None`) so Pylance can work with it, and then wrap return values in `str()` / `bool()` / `int()` to satisfy the declared return type.
- **AsyncMock vs MagicMock for Sync Methods:** If a real method is synchronous (like `EmbeddingProvider.embed_batch`), mocking it with `AsyncMock` causes the mock to return a coroutine instead of the raw value. This silently passes type checks but fails at runtime with `TypeError: 'coroutine' object is not subscriptable`. Always use `MagicMock` for sync methods and `AsyncMock` only for `async def` methods.
