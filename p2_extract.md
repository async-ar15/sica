### PHASE 2.1 — SESSION MEMORY (MEMORY.MD + CHECKPOINT + TASK LOGS)

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1 complete
**ESTIMATED DURATION:** 3 hours
**GOAL:** A `SessionMemory` class that reads/writes `MEMORY.md` for persistent facts, `checkpoint.md` for crash recovery, per-task Markdown logs, and a `notes.md` scratchpad — the agent's long-term human-readable memory.

#### FILES TO CREATE:

##### `agent/memory/session.py`
- **`CheckpointData` BaseModel:** version, current_goal, current_state, iteration_count, last_error, files_modified, current_hypothesis, tried_hypotheses, task_id, timestamp
- **`MemoryCategory` StrEnum:** ARCHITECTURE, PATTERN, ERROR, CONVENTION, FACT
- **`SessionMemory` class:**
  - `__init__(memory_dir: str = "memory/")`:
    - `self.memory_dir = Path(memory_dir)`
    - Create directory if not exists
    - Create `task_logs/` subdirectory if not exists
  - **MEMORY.md operations:**
    - `read_memory() -> str`:
      - Read `memory/MEMORY.md`
      - If file doesn't exist: create with header template and return it
      - Header template: `# Agent Memory\n\n## Architecture\n\n## Patterns\n\n## Errors\n\n## Conventions\n\n## Facts\n`
    - `append_fact(fact: str, category: MemoryCategory, source_task: str)`:
      - Format: `- [{category}] {fact} (from task: {source_task}, {ISO timestamp})`
      - Read file, find the section header matching category
      - Append under that section
      - Atomic write (`.tmp` + `os.rename()`)
    - `search_memory(query: str) -> list[str]`:
      - Simple case-insensitive substring search across MEMORY.md lines
      - Return matching lines (Phase 2.2 upgrades to FTS5)
    - `get_memory_size() -> int`:
      - Return MEMORY.md file size in bytes
      - Warn if > 50KB (compression needed — `/dream` in Phase 3)
  - **checkpoint.md operations:**
    - `save_checkpoint(data: CheckpointData)`:
      - Serialize `CheckpointData` to structured Markdown:
        ```markdown
        # Checkpoint
        ## Version: {version}
        ## Goal: {goal}
        ## State: {state}
        ## Iteration: {count}
        ## Last Error: {error}
        ## Files Modified: {files}
        ## Hypothesis: {hypothesis}
        ## Tried: {tried_list}
        ## Task ID: {task_id}
        ## Timestamp: {timestamp}
        ```
      - Atomic write: write to `.checkpoint.md.tmp`, then `os.rename()` to `checkpoint.md`
    - `load_checkpoint() -> CheckpointData | None`:
      - Read `memory/checkpoint.md`
      - Parse structured Markdown back into `CheckpointData`
      - If file doesn't exist: return None
      - If file is corrupt (parse error): log warning, rename to `.checkpoint.md.corrupt`, return None
      - If version mismatch: log warning, return None (start fresh)
    - `clear_checkpoint()`:
      - Delete `memory/checkpoint.md` if it exists
  - **task_logs operations:**
    - `create_task_log(task_id: str, goal: str)`:
      - Create `memory/task_logs/{task_id}.md`
      - Header: `# Task: {task_id}\n## Goal: {goal}\n## Started: {ISO timestamp}\n`
    - `append_to_task_log(task_id: str, iteration: int, content: str)`:
      - Append: `\n### Iteration {iteration}\n{content}\n`
      - Content includes: plan summary, code changes, test results, reflection output, timing, cost
    - `get_task_log(task_id: str) -> str`:
      - Read and return the full task log
    - `list_task_logs() -> list[str]`:
      - List all `.md` files in `memory/task_logs/`
      - Return task IDs (filenames without extension)
  - **notes.md operations:**
    - `write_note(content: str)`:
      - Overwrite `memory/notes.md` (scratchpad, not append)
      - Atomic write
    - `read_notes() -> str`:
      - Read current notes
      - Return empty string if file doesn't exist
- **Edge cases:**
  - Platform-specific file locking: use `fcntl.flock()` on Linux/macOS, `msvcrt.locking()` on Windows. Wrap in a context manager `@contextmanager file_lock(path)`.
  - MEMORY.md growing too large: warn when > 50KB via logging
  - Atomic checkpoint write prevents corruption if the process crashes mid-write
  - `os.rename()` is NOT atomic across filesystems — ensure temp file is in same directory

##### `tests/test_session_memory.py`
- `test_read_memory_creates_template_if_missing`: Verify header template created
- `test_append_fact_under_correct_section`: Append architecture fact, verify it's under `## Architecture`
- `test_append_fact_format`: Verify format includes category, fact, source_task, timestamp
- `test_search_memory_finds_matches`: Append 5 facts, search for keyword, verify correct matches
- `test_search_memory_case_insensitive`: Search with different case, verify match
- `test_save_checkpoint_creates_file`: Save checkpoint, verify file exists
- `test_load_checkpoint_returns_data`: Save then load, verify fields match
- `test_load_checkpoint_returns_none_if_missing`: Verify None when no checkpoint
- `test_load_checkpoint_handles_corrupt_file`: Write garbage to checkpoint, verify None returned
- `test_clear_checkpoint_deletes_file`: Save, clear, verify file gone
- `test_checkpoint_atomic_write`: Verify temp file pattern (no partial writes)
- `test_create_task_log`: Create log, verify file exists with header
- `test_append_to_task_log`: Create and append, verify content
- `test_list_task_logs`: Create 3 logs, verify list returns all 3
- `test_write_and_read_notes`: Write note, read back, verify content

#### ACCEPTANCE CRITERIA:

- [ ] `from agent.memory.session import SessionMemory, CheckpointData, MemoryCategory` works
- [ ] `MEMORY.md` is created with correct section headers on first read
- [ ] Facts are appended under the correct section header
- [ ] Checkpoint save/load roundtrips correctly
- [ ] Corrupt checkpoints return None (no crash)
- [ ] Task logs are created and appended correctly
- [ ] All 15 test cases pass
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/memory/` returns 0 errors
- [ ] `mypy agent/memory/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_session_memory.py -v` — all tests pass
2. Run `uv run python -c "from agent.memory.session import SessionMemory, MemoryCategory; sm = SessionMemory(); sm.append_fact('Python uses GIL', MemoryCategory.FACT, 'test-001'); print(sm.read_memory())"` — should show the fact under `## Facts`
3. Verify `memory/MEMORY.md` exists and is readable Markdown
4. Run full suite: `uv run pytest tests/ -v` — all tests pass (including Phase 1)

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT use a full Markdown parser to read/write MEMORY.md. Use simple string operations and regex. Markdown parsers are brittle with custom formats.
- Do NOT forget atomic writes. Write to `.tmp`, then `os.rename()`. A crash mid-write WILL corrupt the checkpoint.
- Do NOT use `json.dumps()` for checkpoint — use structured Markdown. The checkpoint must be human-readable.
- Do NOT create the temp file in `/tmp/` — it must be in the same directory as the target for `os.rename()` to be atomic.

---

### PHASE 2.2 — SQLITE FTS5 INDEXED MEMORY

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2.1 (SessionMemory)
**ESTIMATED DURATION:** 2.5 hours
**GOAL:** A `IndexedMemory` class backed by SQLite FTS5 that provides sub-millisecond full-text search across all memory entries with porter stemming and unicode support.

#### FILES TO CREATE:

##### `agent/memory/indexed.py`
- **`MemoryEntry` BaseModel:** content, source, category, project, task_id, created_at
- **`IndexedMemory` class:**
  - `__init__(db_path: str = "memory/memory_index.db")`:
    - `self.db_path = Path(db_path)`
    - Create parent directory if not exists
    - Call `self.initialize()`
  - `initialize()`:
    - Connect to SQLite
    - Create FTS5 virtual table:
      ```sql
      CREATE VIRTUAL TABLE IF NOT EXISTS memory_index USING fts5(
          content,
          source,
          category,
          project,
          task_id,
          created_at,
          tokenize='porter unicode61 tokenchars ._'
      );
      ```
    - The `tokenchars='._'` ensures dotted identifiers like `auth.middleware.validate_token` are treated as single tokens
  - `_get_connection() -> contextmanager`:
    - Return `sqlite3.connect(self.db_path)` wrapped in `@contextmanager`
    - Auto-commit on exit, close connection
  - `index(entry: MemoryEntry)`:
    - Insert entry into FTS5 table
    - Use parameterized query (prevent SQL injection)
  - `index_batch(entries: list[MemoryEntry])`:
    - Use `executemany` for bulk insert
  - `search(query: str, category: str | None = None, limit: int = 10) -> list[MemoryEntry]`:
    - Escape special FTS5 characters in query (`"`, `*`, etc.)
    - Build query:
      ```sql
      SELECT *, rank FROM memory_index
      WHERE memory_index MATCH ?
      AND (? IS NULL OR category = ?)
      ORDER BY rank
      LIMIT ?
      ```
    - Parse results into `MemoryEntry` objects
    - Return sorted by FTS5 relevance rank
  - `reindex_from_markdown(session_memory: SessionMemory)`:
    - Delete all existing entries: `DELETE FROM memory_index`
    - Read MEMORY.md, parse each `- [category] fact ...` line
    - Read all task logs from `memory/task_logs/`
    - Insert all parsed entries
    - Called by `/dream` (Phase 3) and on demand
  - `get_stats() -> dict`:
    - Return: total_entries, entries_per_category (dict), last_indexed (timestamp)
  - `delete_by_task(task_id: str)`:
    - Delete all entries with matching task_id
- **Edge cases:**
  - FTS5 query syntax errors: wrap query in double quotes for exact phrase, or escape special chars
  - Database corruption: detect on open (`PRAGMA integrity_check`), if corrupt, delete and rebuild from Markdown sources
  - Empty query string: return empty list (don't crash)
  - Unicode content: FTS5 with `unicode61` tokenizer handles this natively

##### `tests/test_indexed_memory.py`
- `test_initialize_creates_database`: Verify db file exists after init
- `test_index_and_search_basic`: Index 3 entries, search for keyword, verify match
- `test_search_with_category_filter`: Index entries in different categories, search with filter
- `test_search_relevance_ranking`: Index entries with varying relevance, verify rank order
- `test_search_dotted_identifiers`: Index `auth.middleware.validate_token`, search for `auth.middleware`, verify match
- `test_search_empty_query_returns_empty`: Verify empty list
- `test_search_no_results`: Search for nonexistent term, verify empty list
- `test_index_batch`: Batch insert 10 entries, verify all searchable
- `test_reindex_from_markdown`: Create MEMORY.md with entries, reindex, verify searchable
- `test_get_stats`: Index entries, verify stats are correct
- `test_delete_by_task`: Index entries with task_id, delete, verify gone
- `test_fts5_special_chars_escaped`: Search with query containing `"` or `*`, verify no crash

#### ACCEPTANCE CRITERIA:

- [ ] `from agent.memory.indexed import IndexedMemory, MemoryEntry` works
- [ ] FTS5 search returns relevant results ranked by relevance
- [ ] Searching for `auth.middleware` finds entries with `auth.middleware.validate_token` (tokenchars working)
- [ ] Category filtering works correctly
- [ ] `reindex_from_markdown()` rebuilds the index from MEMORY.md
- [ ] Special characters in queries don't crash the search
- [ ] All 12 test cases pass
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/memory/` returns 0 errors
- [ ] `mypy agent/memory/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_indexed_memory.py -v` — all tests pass
2. Run `uv run python -c "from agent.memory.indexed import IndexedMemory, MemoryEntry; im = IndexedMemory('memory/test_index.db'); im.index(MemoryEntry(content='auth.middleware handles JWT validation', source='MEMORY.md', category='architecture')); results = im.search('auth.middleware'); print(len(results), results[0].content)"` — should print 1 and the content
3. Verify `memory/test_index.db` exists (clean up after)

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT use FTS5's default tokenizer. You MUST use `tokenchars='._'` — without it, `auth.middleware` is split into two separate tokens and searches break.
- Do NOT forget to escape user-provided queries. FTS5 has special syntax (`*`, `"`, `OR`, `AND`) that will cause parse errors if not escaped.
- Do NOT leave SQLite connections open. Use the context manager pattern (`with self._get_connection() as conn:`).
- Do NOT store the SQLite database in a temp directory. It must persist in `memory/memory_index.db`.

---

### PHASE 2.3 — CHROMADB FAILURE MEMORY + EMBEDDING PROVIDER

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2.1 (SessionMemory)
**ESTIMATED DURATION:** 3 hours
**GOAL:** A `FailureMemory` class backed by ChromaDB that stores past errors with solutions as vector embeddings, enabling semantic similarity search — and an `EmbeddingProvider` that generates local embeddings via `sentence-transformers`.

#### FILES TO CREATE:

##### `providers/embeddings.py`
- **`EmbeddingConfig` BaseModel:** model_name, dimension, max_tokens, normalize
- **`EmbeddingProvider` class:**
  - `__init__(config: EmbeddingConfig | None = None)`:
    - Store config (default: `all-MiniLM-L6-v2`, 384 dims)
    - `self._model = None` — lazy-loaded
  - `_load_model()`:
    - `from sentence_transformers import SentenceTransformer`
    - `self._model = SentenceTransformer(self.config.model_name)`
    - Catch `ImportError`: log warning "sentence-transformers not installed — embeddings disabled"
  - `embed(text: str) -> list[float]`:
    - Lazy-load model on first call
    - Truncate text to `config.max_tokens` (approximate with char count * 0.25)
    - Encode: `self._model.encode(text, normalize_embeddings=config.normalize)`
    - Return as list of floats (384-dim)
  - `embed_batch(texts: list[str]) -> list[list[float]]`:
    - Batch encode for efficiency
    - Return list of embedding vectors
  - `@property dimension -> int`:
    - Return `config.dimension`

##### `agent/memory/failure.py`
- **`FailureRecord` BaseModel:** id, error_signature, error_type, context, root_cause, solution, code_before, code_after, tags, success, task_id, created_at + `to_document()` + `to_metadata()`
- **`FailureMemory` class:**
  - `__init__(persist_dir: str = "memory/chromadb", embedding_provider: EmbeddingProvider | None = None)`:
    - Initialize embedding provider (create new if not provided)
    - Initialize ChromaDB: `chromadb.PersistentClient(path=persist_dir)`
    - Get or create collection: `client.get_or_create_collection("failure_memory", metadata={"hnsw:space": "cosine"})`
    - Catch `ImportError`: set `self._disabled = True`, log warning "ChromaDB not installed — failure memory disabled"
  - `store(record: FailureRecord)`:
    - If disabled: return silently
    - Check for duplicate: search for existing record with same `error_signature` (exact match)
    - If duplicate exists and new record has `success=True`: update the existing record
    - Generate embedding: `self.embedding_provider.embed(record.error_signature + " " + record.context)`
    - `collection.add(ids=[record.id], embeddings=[embedding], metadatas=[record.to_metadata()], documents=[record.to_document()])`
  - `search(error_signature: str, context: str = "", top_k: int = 3, threshold: float = 0.85) -> list[FailureRecord]`:
    - If disabled: return empty list
    - Generate query embedding from `error_signature + " " + context`
    - `results = collection.query(query_embeddings=[embedding], n_results=top_k)`
    - Filter results where distance < (1 - threshold) for cosine
    - Parse results back into `FailureRecord` objects
    - Return sorted by similarity
  - `get_solution_for_error(error_signature: str) -> str | None`:
    - Search for similar errors where `success == True`
    - Return the `solution` field from the most similar successful fix
    - Return None if no successful fix found
  - `prune(max_age_days: int = 30)`:
    - Query all records where `success == False`
    - Delete those older than `max_age_days`
    - Called by `/dream` (Phase 3)
  - `get_stats() -> dict`:
    - Return: total_records, successful_records, failed_records

#### FILES TO MODIFY:

##### `pyproject.toml`
- Add new dependencies: `chromadb>=0.5`, `sentence-transformers>=3.0`, `tree-sitter>=0.22`, `tree-sitter-languages>=1.10`

#### FILES TO CREATE:

##### `tests/test_failure_memory.py`
- `test_store_and_search_finds_similar`: Store a failure, search with similar error, verify found
- `test_search_with_different_error_returns_empty`: Store TypeError, search for ImportError, verify empty (below threshold)
- `test_get_solution_returns_successful_fix`: Store success=True record, call get_solution, verify solution returned
- `test_get_solution_returns_none_for_unsolved`: Store success=False only, verify None
- `test_duplicate_detection_updates`: Store same error twice (first unsolved, then solved), verify only one record (updated)
- `test_threshold_filtering`: Store records with varying similarity, verify threshold filters correctly
- `test_disabled_mode_returns_empty`: Mock ChromaDB ImportError, verify search returns empty, store doesn't crash
- `test_prune_removes_old_failures`: Store old failed records, prune, verify removed
- `test_get_stats`: Store records, verify stats are correct

#### ACCEPTANCE CRITERIA:

- [ ] `from agent.memory.failure import FailureMemory, FailureRecord` works
- [ ] `from providers.embeddings import EmbeddingProvider` works
- [ ] Storing a failure record and searching for a similar error returns the record
- [ ] Threshold filtering works (dissimilar errors are excluded)
- [ ] `get_solution_for_error()` returns past solutions for similar errors
- [ ] Graceful degradation when ChromaDB or sentence-transformers is not installed
- [ ] All 9 test cases pass
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/memory/ providers/` returns 0 errors
- [ ] `mypy agent/memory/ providers/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_failure_memory.py -v` — all tests pass
2. Run a manual test: store a TypeError failure, then search for a similar TypeError, verify it's returned
3. Verify `memory/chromadb/` directory is created with ChromaDB data

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT hardcode the embedding dimension. Read it from `EmbeddingConfig.dimension`. A mismatch between embedding and collection dimensions causes a hard crash.
- Do NOT forget to handle `ImportError` for both `chromadb` and `sentence-transformers`. The agent must function (degraded) without these optional dependencies.
- Do NOT use `chromadb.Client()` (ephemeral). Use `chromadb.PersistentClient()` for persistence across sessions.
- Do NOT embed raw error messages with file paths. Normalize the error signature first to get consistent embeddings.

---

### PHASE 2.4 — SIX-STEP REFLECTION PIPELINE

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2.3 (FailureMemory), Phase 1.2 (LLMProvider), Phase 1.7 (WorkingMemory)
**ESTIMATED DURATION:** 3.5 hours
**GOAL:** A `ReflectionEngine` that implements the 6-step EXTRACT → SEARCH → CLASSIFY → HYPOTHESIZE → SELECT → PLAN pipeline, using past failures to avoid repeating mistakes and explicit hypothesis exclusion to prevent loops.

#### FILES TO CREATE:

##### `agent/reflection/engine.py`
- **`ErrorSignature` BaseModel:** error_type, error_message, file_path, line_number, traceback, normalized_signature
- **`Hypothesis` BaseModel:** summary, confidence, files_to_modify, changes_description, expected_outcome, based_on_past_failure
- **`ErrorCategory` StrEnum:** SYNTAX_ERROR, IMPORT_ERROR, TYPE_ERROR, LOGIC_ERROR, TEST_DESIGN, ENVIRONMENT
- **`ReflectionEngine` class:**
  - `__init__(llm: LLMProvider, failure_memory: FailureMemory, working_memory: WorkingMemory)`:
    - Store references to all dependencies
  - `async reflect(error_output: str, context: IterationSnapshot) -> Hypothesis`:
    - Orchestrate the 6 steps in sequence
    - Return the selected hypothesis
  - **Step 1 — EXTRACT:** `_extract(error_output: str) -> ErrorSignature`:
    - Parse error output with regex to extract:
      - Error type: match `(\w+Error):` or `(\w+Exception):`
      - Error message: the text after the error type
      - File path: match `File "(.+)"` from traceback
      - Line number: match `line (\d+)` from traceback
      - Full traceback: everything from `Traceback (most recent call last):`
    - Call `normalize_signature()` to create the normalized version
  - **Step 2 — SEARCH:** `_search(error: ErrorSignature) -> list[FailureRecord]`:
    - Call `self.failure_memory.search(error.normalized_signature, context="", top_k=3)`
    - Return matching past failures with solutions
  - **Step 3 — CLASSIFY:** `_classify(error: ErrorSignature) -> ErrorCategory`:
    - Use `match` statement on `error.error_type`:
      - `SyntaxError` → `ErrorCategory.SYNTAX_ERROR`
      - `ImportError`, `ModuleNotFoundError` → `ErrorCategory.IMPORT_ERROR`
      - `TypeError`, `AttributeError` → `ErrorCategory.TYPE_ERROR`
      - `AssertionError` (from test) → `ErrorCategory.TEST_DESIGN`
      - `Docker*`, `Permission*` → `ErrorCategory.ENVIRONMENT`
      - Everything else → `ErrorCategory.LOGIC_ERROR`
  - **Step 4 — HYPOTHESIZE:** `async _hypothesize(error: ErrorSignature, category: ErrorCategory, past_failures: list[FailureRecord], tried: set[str]) -> list[Hypothesis]`:
    - Build LLM prompt:
      - System: "You are a debugging expert. Analyze the error and propose fixes."
      - Include: full traceback, error classification, similar past failures and their solutions
      - **CRITICAL exclusion:** "Do NOT suggest any of these approaches, they have already been tried: {list(tried)}"
      - Request structured output: list of `Hypothesis` (via Pydantic response_format)
    - Call `self.llm.complete(task_type="reflection", messages=messages, response_format=list[Hypothesis])`
    - Return list of hypotheses
  - **Step 5 — SELECT:** `_select(hypotheses: list[Hypothesis], tried: set[str]) -> Hypothesis`:
    - Filter out any hypothesis whose normalized summary is in `tried`
    - Sort by confidence (descending)
    - Return highest-confidence untried hypothesis
    - If ALL hypotheses are exhausted: return `Hypothesis(summary="EXHAUSTED", confidence=0.0)`
  - **Step 6 — PLAN:** The selected hypothesis IS the plan. Return it directly.
  - `normalize_signature(message: str) -> str`:
    - Replace file paths (`/path/to/file.py`) with `<FILE>`
    - Replace line numbers (`line 42`) with `line <N>`
    - Replace timestamps (ISO dates) with `<TIMESTAMP>`
    - Lowercase and strip whitespace
- **Edge cases:**
  - LLM refuses to generate hypothesis (safety filter): return generic "retry with different approach" hypothesis
  - All hypotheses exhausted: return `EXHAUSTED` hypothesis — harness checks for this and trips circuit breaker
  - Past failure solution contradicts current context: include full context in prompt so LLM adapts
  - No traceback in error output (e.g., assertion failure): extract what's available, don't crash

##### `tests/test_reflection.py`
- `test_extract_parses_typeerror`: Feed TypeError traceback, verify ErrorSignature fields
- `test_extract_parses_importerror`: Feed ImportError, verify fields
- `test_extract_handles_no_traceback`: Feed bare assertion error, verify no crash
- `test_normalize_strips_paths`: Verify paths replaced with `<FILE>`
- `test_normalize_strips_line_numbers`: Verify line numbers replaced with `<N>`
- `test_classify_syntax_error`: Verify SyntaxError → SYNTAX_ERROR
- `test_classify_import_error`: Verify ImportError → IMPORT_ERROR
- `test_classify_logic_error`: Verify RuntimeError → LOGIC_ERROR
- `test_select_picks_highest_confidence`: Create 3 hypotheses, verify highest picked
- `test_select_excludes_tried`: Create hypotheses, mark one as tried, verify it's skipped
- `test_select_returns_exhausted`: Mark all as tried, verify EXHAUSTED returned
- `test_full_reflect_pipeline`: Mock LLM and FailureMemory, run full pipeline, verify hypothesis returned
- `test_reflect_uses_past_failures`: Mock FailureMemory to return past fix, verify hypothesis references it

#### ACCEPTANCE CRITERIA:

- [ ] `from agent.reflection.engine import ReflectionEngine, Hypothesis, ErrorSignature` works
- [ ] Error extraction correctly parses Python tracebacks
- [ ] Error normalization strips paths, line numbers, timestamps
- [ ] Classification routes errors to correct categories
- [ ] Hypothesis generation excludes already-tried approaches
- [ ] Selection picks highest confidence untried hypothesis
- [ ] `EXHAUSTED` hypothesis is returned when all options tried
- [ ] Past failures are searched and included in hypothesis generation
- [ ] All 13 test cases pass
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/reflection/` returns 0 errors
- [ ] `mypy agent/reflection/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_reflection.py -v` — all tests pass
2. Run full suite: `uv run pytest tests/ -v` — all tests pass

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT skip the hypothesis exclusion step. Without it, the agent will suggest the same fix repeatedly and loop forever.
- Do NOT forget to normalize error signatures before comparison. `TypeError at line 42` and `TypeError at line 87` must be treated as the same error.
- Do NOT use the fast model for reflection. Reflection requires the strong model (`task_type="reflection"`) because it needs deep reasoning.
- Do NOT return raw LLM text as a hypothesis. Always parse into structured `Hypothesis` model.

---

### PHASE 2.5 — FULL CIRCUIT BREAKER (ALL 3 CONDITIONS + BUDGET)

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.6 (basic CircuitBreaker), Phase 2.4 (ErrorSignature normalization)
**ESTIMATED DURATION:** 2 hours
**GOAL:** Upgrade the circuit breaker from max-iterations-only to all 3 conditions (consecutive failures, progress score, budget) plus cost tracking integration.

#### FILES TO MODIFY:

##### `agent/core/circuit_breaker.py`
- **Add `ProgressMetrics` BaseModel:** tests_passing, tests_total, lint_errors, code_diff_size, error_signature_changed
- **Upgrade `CircuitBreakerConfig`:** uncomment and activate max_consecutive_failures, progress_window, min_progress_score, max_cost_per_task_usd
- **Upgrade `BreakerState`:** uncomment and activate consecutive_same_errors, progress_history, total_cost_usd
- **Add 3 new condition methods to `CircuitBreaker`:**
  - `_check_consecutive_failures(state: BreakerState) -> TripReason | None`:
    - If `state.consecutive_same_errors >= self.config.max_consecutive_failures`: return `TripReason.CONSECUTIVE_FAILURES`
    - Else: return None
  - `_check_progress(state: BreakerState) -> TripReason | None`:
    - If `len(state.progress_history) < self.config.progress_window`: return None (not enough data)
    - Compute progress score for each of last `progress_window` iterations:
      - `score = 0.4 * (tests_delta > 0) + 0.3 * (lint_delta < 0) + 0.2 * error_signature_changed + 0.1 * (code_diff_size > 0)`
      - Where deltas are relative to previous iteration
    - If `mean(recent_scores) < self.config.min_progress_score`: return `TripReason.NO_PROGRESS`
    - Else: return None
  - `_check_budget(state: BreakerState) -> TripReason | None`:
    - If `state.total_cost_usd >= self.config.max_cost_per_task_usd`: return `TripReason.BUDGET_EXCEEDED`
    - Else: return None
- **Register all conditions in `__init__`:**
  ```python
  self._conditions = [
      self._check_max_iterations,
      self._check_consecutive_failures,
      self._check_progress,
      self._check_budget,
  ]
  ```

##### `agent/core/budget.py`
- **Upgrade from stub to real implementation:**
  - `BudgetTracker` class:
    - `__init__(max_cost: float = 0.50, max_tokens: int = 100000)`: store limits
    - `record(cost: float, tokens: int)`: accumulate `self._total_cost` and `self._total_tokens`
    - `is_exceeded() -> bool`: check if either limit hit
    - `get_usage() -> dict`: return `{"cost_usd": ..., "tokens": ..., "cost_limit": ..., "token_limit": ..., "cost_percent": ..., "token_percent": ...}`
    - `reset()`: zero out counters

##### `tests/test_circuit_breaker.py` (ADD NEW TESTS)
- Keep all existing Phase 1 tests
- Add:
  - `test_consecutive_failures_trips`: 3 same errors → trip
  - `test_consecutive_failures_resets_on_new_error`: 2 same, 1 different → no trip
  - `test_progress_insufficient_history`: < 3 iterations → no trip (not enough data)
  - `test_progress_no_progress_trips`: 3 iterations with zero progress → trip
  - `test_progress_with_progress_no_trip`: 3 iterations with improving tests → no trip
  - `test_budget_exceeded_trips`: cost > limit → trip
  - `test_budget_not_exceeded`: cost < limit → no trip
  - `test_progress_score_formula`: Verify exact formula: 0.4*tests + 0.3*lints + 0.2*error + 0.1*diff
  - `test_all_conditions_checked_first_wins`: Set up state that trips multiple conditions, verify first one returned

#### ACCEPTANCE CRITERIA:

- [ ] Circuit breaker trips on consecutive failures (3 same errors)
- [ ] Circuit breaker trips on no progress (mean score < 0.1 over window)
- [ ] Circuit breaker trips on budget exceeded
- [ ] Progress score formula is correct: `0.4*tests + 0.3*lints + 0.2*error + 0.1*diff`
- [ ] Insufficient history (< window size) does NOT trip progress check
- [ ] Budget tracker accumulates cost and tokens correctly
- [ ] All 16+ test cases pass (7 Phase 1 + 9 new)
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/core/` returns 0 errors
- [ ] `mypy agent/core/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_circuit_breaker.py -v` — all tests pass
2. Verify progress score calculation manually with known inputs
3. Run full suite: `uv run pytest tests/ -v` — all tests pass

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT check progress before enough iterations exist. The progress window requires N iterations of data — skip the check if `len(progress_history) < progress_window`.
- Do NOT forget to include LLM retry costs in budget tracking. A rate-limited call that retries 3 times costs 3x.
- Do NOT compute progress deltas against the FIRST iteration. Compute against the PREVIOUS iteration.
- Do NOT break existing Phase 1 tests. All 7 existing tests must still pass.

---

### PHASE 2.6 — TREE-SITTER REPO MAP

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 1.1 (dependencies), Phase 2 new dependencies (tree-sitter)
**ESTIMATED DURATION:** 3 hours
**GOAL:** A `RepoMap` class that uses tree-sitter to build a structural summary of any Python project — classes, functions, signatures — in ~500 tokens, enabling the agent to understand codebase structure without reading every file.

#### FILES TO CREATE:

##### `agent/tools/repo_map.py`
- **`Symbol` BaseModel:** name, kind, signature, start_line, end_line, file_path
- **`RepoMap` class:**
  - `__init__()`:
    - Try to import `tree_sitter_languages`: `from tree_sitter_languages import get_parser`
    - Catch `ImportError`: set `self._available = False`, log warning
  - `build(project_dir: str, max_tokens: int = 500) -> str`:
    - Walk all source files in `project_dir`
    - Exclude: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `venv/`, `dist/`, `*.egg-info/`
    - For each `.py` file: call `extract_symbols()`
    - Format as indented tree:
      ```
      agent/core/state_machine.py
        class AgentState(StrEnum)
        class StateSnapshot(BaseModel)
        class StateMachine
          async def transition(event: str) -> AgentState
          def can_transition(event: str) -> bool
          def reset()
      ```
    - Count approximate tokens (chars / 4)
    - If total > `max_tokens`: rank files by name relevance to common patterns, truncate least relevant
    - If `self._available == False`: fall back to file listing (no symbols)
    - Return formatted string
  - `extract_symbols(file_path: str) -> list[Symbol]`:
    - Read file content
    - Parse with tree-sitter Python parser: `parser = get_parser("python"); tree = parser.parse(content_bytes)`
    - Walk AST: find `class_definition`, `function_definition`, `decorated_definition` nodes
    - For each:
      - Extract name from `identifier` child node
      - Extract parameters from `parameters` child node
      - Extract return type from `type` child node (if present)
      - Extract line range from `start_point` / `end_point`
      - Build signature string: `def name(param1: type1, param2: type2) -> return_type`
    - Return list of `Symbol`
  - `get_function_source(file_path: str, function_name: str) -> str | None`:
    - Parse file, find matching function/method node by name
    - Extract and return full source code (from start_point to end_point)
    - Used by Level 3 fault localization (Phase 2.7)
    - Return None if function not found
  - `get_class_source(file_path: str, class_name: str) -> str | None`:
    - Same as above for classes
- **Edge cases:**
  - tree-sitter parser not available: fall back to regex-based symbol extraction (match `class ` and `def ` lines)
  - File encoding errors (non-UTF-8): try `utf-8`, `latin-1`, `cp1252` in order; skip if all fail
  - Very large files (> 10K lines): extract only top-level symbols, skip nested functions
  - Symlinks: skip (don't follow)
  - Binary files: detect (null bytes in first 8KB), skip

##### `tests/test_repo_map.py`
- `test_build_generates_tree`: Create a temp project with Python files, build map, verify structure
- `test_extract_symbols_finds_classes`: Parse a file with classes, verify class symbols extracted
- `test_extract_symbols_finds_functions`: Parse a file with functions, verify function symbols extracted
- `test_extract_symbols_includes_signatures`: Verify parameters and return types are in signature
- `test_extract_symbols_includes_line_numbers`: Verify start_line and end_line
- `test_build_excludes_git_directory`: Create `.git/` dir with files, verify excluded
- `test_build_excludes_pycache`: Create `__pycache__/`, verify excluded
- `test_build_respects_max_tokens`: Create large project, verify output within token limit
- `test_get_function_source`: Create file with function, call get_function_source, verify full source
- `test_get_function_source_not_found`: Call with nonexistent function, verify None
- `test_fallback_without_treesitter`: Mock tree-sitter unavailable, verify fallback output
- `test_binary_file_skipped`: Create binary file, verify it's skipped

#### ACCEPTANCE CRITERIA:

- [ ] `from agent.tools.repo_map import RepoMap, Symbol` works
- [ ] `build()` generates a readable structural tree of a Python project
- [ ] Symbols include classes, functions, signatures, and line numbers
- [ ] `.git/`, `__pycache__/`, `.venv/` are excluded
- [ ] `max_tokens` limit is respected
- [ ] `get_function_source()` returns full function source code
- [ ] Fallback works when tree-sitter is unavailable
- [ ] All 12 test cases pass
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/tools/` returns 0 errors
- [ ] `mypy agent/tools/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_repo_map.py -v` — all tests pass
2. Run `uv run python -c "from agent.tools.repo_map import RepoMap; rm = RepoMap(); print(rm.build('agent/'))"` — should print structural tree of the agent package
3. Verify output looks like the expected format (indented tree with signatures)

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT pin `tree-sitter` and `tree-sitter-languages` to different major versions. A mismatch causes `LanguageError: Incompatible Language version`.
- Do NOT try to parse binary files with tree-sitter. Detect binary (null bytes) first.
- Do NOT read entire 10K+ line files into memory for symbol extraction. Use tree-sitter's efficient parsing which operates on the AST, not the raw text.
- Do NOT include function bodies in the repo map. Only signatures. The repo map must be ~500 tokens, not 50,000.

---

### PHASE 2.7 — HIERARCHICAL FAULT LOCALIZATION

**STATUS:** NOT STARTED
**DEPENDS ON:** Phase 2.6 (RepoMap), Phase 2.4 (ErrorSignature), Phase 1.2 (LLMProvider)
**ESTIMATED DURATION:** 3.5 hours
**GOAL:** A `FaultLocalizer` that narrows a bug from the entire repo to the exact lines to edit through a 3-level funnel (file → element → edit-line), using ~2,700 tokens instead of ~200,000.

#### FILES TO CREATE:

##### `agent/tools/fault_localizer.py`
- **`EditLocation` BaseModel:** file_path, start_line, end_line, element_name, reason, confidence
- **`LocalizationResult` BaseModel:** level1_files, level2_elements, level3_edit_locations, total_tokens_used
- **`FaultLocalizer` class:**
  - `__init__(llm: LLMProvider, repo_map: RepoMap)`:
    - Store references
  - `async localize(error: ErrorSignature, repo_map_str: str, project_dir: str) -> LocalizationResult`:
    - Run all 3 levels in sequence
    - Track total tokens used across all calls
    - Return `LocalizationResult`
  - **Level 1 — File-level** (~200 tokens):
    - `async _level1_files(error: ErrorSignature, repo_map_str: str) -> list[str]`:
      - Extract files mentioned in traceback
      - Filter out non-project files (`_filter_project_files()`)
      - Build prompt: error traceback + file tree (paths only, from repo map)
      - LLM call (strong model): "Rank the top 5 files most likely to contain the bug."
      - Response format: list of `{file_path, confidence, reasoning}`
      - Return top 5 file paths
  - **Level 2 — Element-level** (~500 tokens per file):
    - `async _level2_elements(error: ErrorSignature, candidate_files: list[str], project_dir: str) -> list[dict]`:
      - For each candidate file:
        - Get tree-sitter symbols (signatures only, NOT full code)
        - Build prompt: error + function/class signatures
        - LLM call (strong model): "Which functions or classes are most related to the bug?"
        - Response: list of `{element_name, confidence}`
      - Return top 3 elements per file
  - **Level 3 — Edit-level** (~2000 tokens total):
    - `async _level3_edits(error: ErrorSignature, candidate_elements: list[dict], project_dir: str) -> list[EditLocation]`:
      - For each candidate element:
        - Get FULL source code via `repo_map.get_function_source()` / `get_class_source()`
        - Build prompt: error + full source of candidate
        - LLM call (strong model): "Identify the exact lines that need to change."
        - Response: `EditLocation` with file_path, start_line, end_line, reason, confidence
      - Return list of `EditLocation`
  - `_filter_project_files(traceback_files: list[str], project_dir: str) -> list[str]`:
    - Keep only files inside `project_dir`
    - Remove paths containing `site-packages/`, `lib/python`, system paths
    - Return filtered list
- **Edge cases:**
  - No traceback: fall back to keyword search in repo map for error message text
  - Level 1 returns 0 candidates: search for error message string across all project files
  - Level 2 returns 0 candidates for a file: skip to next file
  - LLM returns file paths that don't exist: validate each path, skip non-existent
  - LLM returns line numbers out of range: clamp to valid range

##### `tests/test_fault_localizer.py`
- `test_filter_project_files_keeps_project_only`: Filter list with both project and site-packages files
- `test_filter_project_files_removes_site_packages`: Verify site-packages paths removed
- `test_level1_returns_top_5_files`: Mock LLM, verify top 5 returned
- `test_level2_returns_elements_per_file`: Mock LLM, verify elements per file
- `test_level3_returns_edit_locations`: Mock LLM, verify edit locations with line ranges
- `test_full_localization_pipeline`: Mock all LLM calls, run full pipeline, verify LocalizationResult
- `test_total_tokens_tracked`: Run pipeline, verify total_tokens_used is sum of all calls
- `test_no_traceback_fallback`: Pass error without traceback, verify fallback to keyword search
- `test_nonexistent_file_skipped`: LLM returns nonexistent file, verify skipped without crash
- `test_level1_zero_candidates_fallback`: Mock LLM returning empty list, verify fallback

#### ACCEPTANCE CRITERIA:

- [ ] `from agent.tools.fault_localizer import FaultLocalizer, EditLocation, LocalizationResult` works
- [ ] 3-level pipeline narrows from files → elements → lines
- [ ] Non-project files (site-packages) are filtered out
- [ ] Total tokens tracked across all 3 levels
- [ ] Fallback behavior works when traceback is missing
- [ ] All 10 test cases pass
- [ ] All Phase 1 tests still pass
- [ ] `ruff check agent/tools/` returns 0 errors
- [ ] `mypy agent/tools/ --strict` returns 0 errors

#### MANUAL TEST STEPS:

1. Run `uv run pytest tests/test_fault_localizer.py -v` — all tests pass
2. Run full suite: `uv run pytest tests/ -v` — all tests pass

#### COMMON MISTAKES TO AVOID IN THIS PHASE:

- Do NOT read full file contents at Level 1 or Level 2. Level 1 uses only file NAMES. Level 2 uses only SIGNATURES. Full source is Level 3 only. This is the entire point — token efficiency.
- Do NOT parallelize the levels. They are sequential: Level 2 depends on Level 1 output, Level 3 depends on Level 2 output.
- Do NOT forget to filter `site-packages/` paths from tracebacks. Library internals are not candidate fix locations.
- Do NOT use the fast model for fault localization. Use the strong model — it requires nuanced code understanding.

---

