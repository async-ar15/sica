import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from agent.memory.session import SessionMemory


class MemoryEntry(BaseModel):
    """A memory fact or snippet for full-text search indexing."""
    content: str
    source: str
    category: str
    project: str = "default"
    task_id: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IndexedMemory:
    """Provides fast FTS5-based full-text search over memory facts and logs."""

    def __init__(self, db_path: str = "memory/memory_index.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provides a managed database connection."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Sets up the SQLite database and FTS5 virtual table."""
        # Check for corruption before proceeding
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result is None or result[0] != "ok":
                    raise sqlite3.DatabaseError("Database integrity check failed.")
        except (sqlite3.DatabaseError, sqlite3.OperationalError):
            # Database is missing or corrupt. Delete it if it exists.
            if self.db_path.exists():
                self.db_path.unlink()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_index USING fts5(
                    content,
                    source,
                    category,
                    project,
                    task_id,
                    created_at,
                    tokenize="porter unicode61 tokenchars '._'"
                );
            """)

    def index(self, entry: MemoryEntry) -> None:
        """Indexes a single memory entry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_index (content, source, category, project, task_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry.content,
                entry.source,
                entry.category,
                entry.project,
                entry.task_id,
                entry.created_at.isoformat()
            ))

    def index_batch(self, entries: list[MemoryEntry]) -> None:
        """Indexes multiple memory entries efficiently."""
        if not entries:
            return

        data = [
            (e.content, e.source, e.category, e.project, e.task_id, e.created_at.isoformat())
            for e in entries
        ]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO memory_index (content, source, category, project, task_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, data)

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[MemoryEntry]:
        """Searches memory using FTS5 MATCH syntax, ordered by relevance rank."""
        if not query.strip():
            return []

        # Escape FTS5 special characters that could cause syntax errors
        # If the user typed double quotes, let's just escape them to avoid unbalanced quote errors,
        # or we could enclose the whole query in double quotes.
        safe_query = query.replace('"', '""')
        # Append * to allow prefix matching on dotted identifiers
        safe_query = f'"{safe_query}"*'

        sql = "SELECT content, source, category, project, task_id, created_at FROM memory_index WHERE memory_index MATCH ?"
        params: list[str | int] = [safe_query]

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                for row in cursor.fetchall():
                    results.append(MemoryEntry(
                        content=row[0],
                        source=row[1],
                        category=row[2],
                        project=row[3],
                        task_id=row[4],
                        created_at=datetime.fromisoformat(row[5])
                    ))
        except sqlite3.OperationalError:
            # Could be a FTS5 syntax error with the query string even after basic escaping
            # Return empty if query parsing fails
            return []

        return results

    def reindex_from_markdown(self, session_memory: SessionMemory) -> None:
        """Rebuilds the index completely from MEMORY.md and task logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_index")

        entries = []

        # Parse MEMORY.md
        memory_content = session_memory.read_memory()

        # Format is typically: - [category] fact (from task: task_id, timestamp)
        # E.g. - [architecture] python uses GIL (from task: t1, 2026-08-16T12:00:00Z)
        fact_pattern = re.compile(r"^- \[([^\]]+)\] (.*?) \(from task: ([^,]+), (.*?)\)")

        for line in memory_content.splitlines():
            line = line.strip()
            match = fact_pattern.match(line)
            if match:
                cat, content, task_id, ts_str = match.groups()
                try:
                    ts = datetime.fromisoformat(ts_str)
                except ValueError:
                    ts = datetime.now(timezone.utc)

                entries.append(MemoryEntry(
                    content=content,
                    source="MEMORY.md",
                    category=cat,
                    task_id=task_id,
                    created_at=ts
                ))

        # Parse Task Logs
        for task_id in session_memory.list_task_logs():
            log_content = session_memory.get_task_log(task_id)
            # A simplistic approach: store the entire log as one chunk, or per iteration.
            # Let's chunk by iterations to make it searchable.
            iterations = log_content.split("### Iteration ")

            # The first chunk is the header
            if len(iterations) > 0:
                header = iterations[0]
                entries.append(MemoryEntry(
                    content=header.strip(),
                    source=f"task_logs/{task_id}.md",
                    category="task_header",
                    task_id=task_id
                ))

            # The rest are iterations
            for it_chunk in iterations[1:]:
                # The first line is the iteration number, rest is content
                lines = it_chunk.splitlines()
                if not lines:
                    continue
                it_num = lines[0].strip()
                content = "\n".join(lines[1:]).strip()
                if content:
                    entries.append(MemoryEntry(
                        content=content,
                        source=f"task_logs/{task_id}.md",
                        category=f"iteration_{it_num}",
                        task_id=task_id
                    ))

        self.index_batch(entries)

    def get_stats(self) -> dict[str, int | str | dict[str, int]]:
        """Returns database statistics."""
        stats: dict[str, int | str | dict[str, int]] = {
            "total_entries": 0,
            "entries_per_category": {}
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM memory_index")
            row = cursor.fetchone()
            if row:
                stats["total_entries"] = row[0]

            cursor.execute("SELECT category, COUNT(*) FROM memory_index GROUP BY category")
            cat_stats = {}
            for row in cursor.fetchall():
                cat_stats[row[0]] = row[1]

            stats["entries_per_category"] = cat_stats

            # Fetch latest created_at
            cursor.execute("SELECT MAX(created_at) FROM memory_index")
            row = cursor.fetchone()
            stats["last_indexed"] = row[0] if row and row[0] else ""

        return stats

    def delete_by_task(self, task_id: str) -> None:
        """Deletes all entries associated with a specific task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_index WHERE task_id = ?", (task_id,))
