# Phase Status Tracker

| Phase | Description | Status |
|-------|-------------|--------|
| 1.1 | Repo Scaffold and Dependency Installation | DONE |
| 1.2 | LLM Provider Abstraction | DONE |
| 1.3 | Eight-State Finite State Machine | DONE |
| 1.4 | Docker Sandbox | DONE |
| 1.5 | Agent-Computer Interface | DONE |
| 1.6 | Circuit Breaker | DONE |
| 1.7 | Working Memory | DONE |
| 1.8 | Rich CLI | DONE |
| 1.9 | Agent Harness | DONE |
| 1.10 | Trajectory Logger | DONE |
| 1.11 | Integration & Cleanup | DONE |
| 2.1 | Session Memory (MEMORY.md) | DONE |
| 2.2 | Indexed Memory (SQLite FTS5) | DONE |
| 2.3 | Failure Memory (ChromaDB) | DONE |
| 2.4 | Reflection Engine Pipeline | DONE |
| 2.5 | Circuit Breaker Upgrades | DONE |
| 2.6 | Repo Map (AST) | DONE |
| 2.7 | Hierarchical Fault Localization | DONE |
| 2.8 | Orchestration Harness Wiring & Checkpointing | DONE |
| 2.9 | Permission Modes (Gate & CLI) | DONE |
| 2.10 | Static Analysis Runner (ruff/mypy/bandit) | DONE |
| 2.11 | Integration Smoke Test | DONE |
| 3.1 | Architect Agent (FSM Planning State) | DONE |
| 3.2 | Planner Enhancements & DAG Validation | DONE |
| 3.3 | Worker Agent (FSM Coding State) | DONE |
| 3.4 | Judge Agent (FSM Review State) | DONE |
| 3.5 | Context Compaction & Summarization | DONE |
| 3.6 | Multi-Candidate Fix Search (N=3) | DONE |
| 3.7 | Cost/Token Budget System | DONE |
| 3.8 | MCP (Model Context Protocol) Support | DONE |
| 3.9 | Git Integration | DONE |
| 3.10 | Evaluation Harness | DONE |
| 3.11 | Trajectory Logging Enhancements | DONE |
| 3.12 | Error Boundaries & Loading States | DONE |
| 3.13 | README Generation | DONE |
| 3.14 | Sandbox Hardening | DONE |
| 3.15 | Final E2E Integration Testing & Polish | DONE |
## Blockers Log

| Date | Phase | Blocker Description | Resolution |
|------|-------|---------------------|------------|
| 2026-08-16 | 1.1 | `uv` not found | Installed `uv` via pip locally |
| 2026-08-17 | 2.8 | `docker-py` strict typing issues in IDE (Pyright) vs MyPy | Passed dictionary unpacked kwargs dynamically (`**log_args: Any`) to suppress IDE errors without violating mypy strict. |
| 2026-08-17 | 2.8 | Pydantic validation error on FSM `iteration_count` | Updated `StateMachine.transition` kwargs mapping to explicitly receive and pass `iteration_count=iteration`. |
| 2026-08-17 | 2.8 | `LLMProvider` mismatch: `generate` vs `complete` | Replaced legacy `generate` calls in `harness.py` with `complete` and fixed `error` transition state. |
| 2026-08-17 | 2.8 | Rich `Table` string parsing crash for composite themes | Defined `"primary_bold"` directly in the `Theme` dict instead of using inline `"bold primary"`. |
| 2026-08-17 | 2.9 | `uv` package missing in user's Git Bash environment | Explicitly ran `python -m pip install uv` inside the active `.venv` to ensure `uv` is available. |
| 2026-08-17 | 2.9 | Circular import between `aci.py` and `permissions.py` | Moved `PermissionGate` import in `aci.py` under `if TYPE_CHECKING` and used forward reference in type hint. |
| 2026-08-17 | 2.9 | `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f3af'` on Windows | Reconfigured `sys.stdout` to use `utf-8` encoding at the start of `cli.py` on `win32` platforms. |
| 2026-08-17 | 2.10 | Docker build command failure (`open Dockerfile: no such file`) | Specified the exact Dockerfile name `-f docker/Dockerfile.sandbox` instead of relying on default `Dockerfile`. |
| 2026-08-17 | 2.11 | `docker-py` threw unexpected keyword argument `demux` error during `container.logs()` | Removed `demux=True` and manually decoded the mixed byte stream returned by default `logs(stdout=True, stderr=True)`. |

## Deviations/Decisions Log

| Date | Phase | Decision | Rationale |
|------|-------|----------|-----------|
| 2026-08-16 | 1.1 | Used `[dependency-groups] dev` instead of `[tool.uv] dev-dependencies` | Replaced deprecated key to suppress uv warnings |
| 2026-08-16 | 1.2 | Handled LiteLLM typing issues via ignore tags | litellm module typings do not explicitly export its exceptions, so `# type: ignore[attr-defined]` was used to satisfy strict mypy checks. |
| 2026-08-17 | 2.6 | Used Python's built-in `ast` module instead of Tree-Sitter | `tree-sitter-languages` failed to compile and load on Python 3.13 due to missing binaries. `ast` serves as an elegant, zero-dependency fallback for parsing Python structures. |
| 2026-08-17 | 2.10 | Replaced `pytest-mock` `mocker` fixture with standard `unittest.mock` | Avoided adding another testing dependency (`pytest-mock`) by simply utilizing the built-in `unittest.mock.AsyncMock` and `Mock`. |
| 2026-08-17 | 3.10 | Eval Tasks Externalized to YAML | Kept evaluation tasks as separate YAML files in `eval/tasks` rather than hardcoding them to allow easy external contributions. |
| 2026-08-17 | 3.12 | CLI Fallbacks Implemented | Added global try-except for optional dependencies and YAML syntax error handling to prevent hard crashes. |
| 2026-08-17 | 3.14 | Auto-Build Sandbox in Python | Avoided requiring the user to manually run `docker build` by handling the `ImageNotFound` exception inside `DockerSandbox` and invoking `client.images.build()` natively through Python. |
| 2026-08-17 | 3.15 | Phase 3 Test Suite Run | Re-ran entire test suite natively verifying 208 passing tests successfully after 3.12 error boundary integrations. |
| 2026-08-17 | 3.9 | Safe Git Stashing | Explicitly enforced the GitManager to `git add` precise files modified by the task and avoid `git add -a` to safeguard the user's concurrent, uncommitted work in the repository. |
| 2026-08-17 | 3.15 | Strict Typing & CLI Wiring Fixes | Resolved static analysis errors caught by MyPy/Pyright (e.g. unannotated empty lists, implicit optionals, magic mock attributes in `tests`, async/await mismatches in `distill.py`/`dream.py`, type casting on FTS stats, and missing dependency wiring in `cli.py`). |
| 2026-08-17 | 3.15 | Pyright CLI Cleanup | Resolved residual Pyright CLI errors: removed rogue `stack_trace` kwargs in `test_fix_searcher.py`, cast dynamic dict responses in `dream.py` to `int(str(...))`, and ignored `yaml` and `TextIO` attribute access in `cli.py`. |
| 2026-08-17 | 3.15 | VS Code Pylance Polish | Fixed Pylance IDE specific squiggles: swapped `# pyright: ignore` for universally supported `# type: ignore` in `git_tools.py` and `sandbox.py`, added `from __future__ import annotations` for forward references in `aci.py`, and added `| None` to `_send_jsonrpc` in `mcp.py`. |
| 2026-08-17 | 3.15 | Deep Pylance Unknown-Type Fixes | Typed `self.repo` as `Any` in `git_tools.py` to eliminate Pylance `Unknown` narrowing failures on `working_tree_dir` and `git.diff()`. Cast `json.loads` result in `mcp.py` with explicit `dict[str, Any]` annotation. Annotated `response: Any` in `fix_searcher.py` to prevent implicit-Any returns. Removed unreachable dead code (`schema.extend`) in `aci.py`. Removed overzealous `str()` casts in `fix_searcher.py`. Fixed test mocks: changed `AsyncMock` → `MagicMock` for sync `embed_batch` in `test_distill.py`/`test_dream.py`, and rewrote `test_fix_searcher.py` to use `analyzer.analyze()` instead of removed `run_analysis()`. All 208 tests pass. |
