import logging
import os
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from agent.memory.failure import FailureMemory
from agent.memory.indexed import IndexedMemory
from agent.memory.session import SessionMemory, file_lock
from providers.embeddings import EmbeddingProvider
from providers.llm import LLMProvider

logger = logging.getLogger(__name__)

class DreamReport(BaseModel):
    duplicates_merged: int = 0
    paths_validated: int = 0
    stale_paths: int = 0
    logs_compressed: int = 0
    failures_pruned: int = 0
    total_entries_after: int = 0
    summary: str = ""

class DreamEngine:
    def __init__(
        self,
        session: SessionMemory,
        indexed: IndexedMemory,
        failure: FailureMemory,
        embeddings: EmbeddingProvider,
        llm: LLMProvider
    ):
        self.session = session
        self.indexed = indexed
        self.failure = failure
        self.embeddings = embeddings
        self.llm = llm

    async def run(self, workspace_dir: str) -> DreamReport:
        # Step 1: Scan
        inventory = self._scan()
        if inventory["total_entries"] == 0:
            return DreamReport(summary="No memory to maintain")

        metrics = {"total_entries_before": inventory["total_entries"]}

        # Step 2: Deduplicate
        metrics["duplicates_merged"] = await self._deduplicate()

        # Step 3: Validate
        val, stale = self._validate_paths(workspace_dir)
        metrics["paths_validated"] = val
        metrics["stale_paths"] = stale

        # Step 4: Compress
        metrics["logs_compressed"] = await self._compress_old_logs()

        # Step 5: Prune
        metrics["failures_pruned"] = self._prune_failures()

        # Step 6: Reindex
        self._reindex()

        # Step 7: Report
        return await self._generate_report(metrics)

    def _scan(self) -> dict[str, Any]:
        count = 0

        # FTS5 entries
        try:
            stats = self.indexed.get_stats()
            count += int(str(stats.get("total_entries", 0)))
        except Exception:
            pass

        # MEMORY.md lines
        mem = self.session.read_memory()
        lines = [line for line in mem.splitlines() if line.startswith("- [")]
        count += len(lines)

        return {"total_entries": count}

    async def _deduplicate(self) -> int:
        merges = 0
        try:
            with self.indexed._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT content FROM memory_index")
                contents = [row[0] for row in cursor.fetchall()]

            if not contents:
                return 0

            embeddings = self.embeddings.embed_batch(contents)

            # Simple pairwise cosine similarity > 0.92
            import numpy as np
            to_delete = set()
            for i in range(len(embeddings)):
                if i in to_delete: continue
                for j in range(i + 1, len(embeddings)):
                    if j in to_delete: continue

                    e1 = np.array(embeddings[i])
                    e2 = np.array(embeddings[j])
                    similarity = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))
                    if similarity > 0.92:
                        # Keep the longer one
                        if len(contents[i]) > len(contents[j]):
                            to_delete.add(j)
                        else:
                            to_delete.add(i)

            # Delete from SQLite
            with self.indexed._get_connection() as conn:
                for idx in to_delete:
                    conn.execute("DELETE FROM memory_index WHERE content = ?", (contents[idx],))
                    merges += 1

        except Exception as e:
            logger.warning(f"Deduplication failed: {e}")

        return merges

    def _validate_paths(self, workspace_dir: str) -> tuple[int, int]:
        val = 0
        stale = 0
        content = self.session.read_memory()
        lines = content.splitlines()
        new_lines = []
        changed = False

        for line in lines:
            if line.startswith("- [") and "`" in line:
                import re
                paths = re.findall(r'`([^`]+)`', line)
                line_changed = False
                for p in paths:
                    if "/" in p or "." in p:
                        val += 1
                        if not os.path.exists(os.path.join(workspace_dir, p)):
                            stale += 1
                            if "[PATH NOT FOUND]" not in line:
                                line = line + " [PATH NOT FOUND]"
                                line_changed = True
                if line_changed:
                    changed = True
            new_lines.append(line)

        if changed:
            with file_lock(self.session.memory_file):
                self.session._atomic_write(self.session.memory_file, "\n".join(new_lines) + "\n")

        return val, stale

    async def _compress_old_logs(self, max_age_days: int = 7) -> int:
        compressed = 0
        archive_dir = self.session.task_logs_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(UTC)
        for log_id in self.session.list_task_logs():
            log_file = self.session.task_logs_dir / f"{log_id}.md"
            if log_file.exists():
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=UTC)
                if (now - mtime).days > max_age_days:
                    # Summarize
                    content = log_file.read_text(encoding="utf-8")
                    prompt = "Summarize the following task log in one paragraph. PRESERVE: paths, errors, decisions.\n\n" + content

                    messages = [
                        {"role": "system", "content": "You are a summarizing assistant."},
                        {"role": "user", "content": prompt}
                    ]

                    try:
                        response = await self.llm.complete(
                            task_type="context_compaction",
                            messages=messages
                        )
                        summary = response.content

                        # Move to archive
                        import shutil
                        shutil.move(log_file, archive_dir / f"{log_id}.md")

                        # Write summary
                        self.session._atomic_write(log_file, f"# Task: {log_id}\n\n## Summary\n{summary}\n")
                        compressed += 1
                    except Exception as e:
                        logger.warning(f"Failed to compress {log_id}: {e}")

        return compressed

    def _prune_failures(self, max_age_days: int = 30) -> int:
        try:
            return self.failure.prune(max_age_days)
        except Exception:
            return 0

    def _reindex(self) -> None:
        try:
            self.indexed.reindex_from_markdown(self.session)
        except Exception:
            pass

    async def _generate_report(self, metrics: dict[str, Any]) -> DreamReport:
        # Very simple summary for now
        summary = (
            f"Dream cycle complete. "
            f"Merged {metrics.get('duplicates_merged', 0)} duplicates. "
            f"Validated {metrics.get('paths_validated', 0)} paths ({metrics.get('stale_paths', 0)} stale). "
            f"Compressed {metrics.get('logs_compressed', 0)} logs. "
            f"Pruned {metrics.get('failures_pruned', 0)} failures."
        )

        try:
            # We can get total entries from indexed memory
            total_after = int(str(self.indexed.get_stats().get("total_entries", 0)))
        except Exception:
            total_after = 0

        return DreamReport(
            duplicates_merged=metrics.get("duplicates_merged", 0),
            paths_validated=metrics.get("paths_validated", 0),
            stale_paths=metrics.get("stale_paths", 0),
            logs_compressed=metrics.get("logs_compressed", 0),
            failures_pruned=metrics.get("failures_pruned", 0),
            total_entries_after=total_after,
            summary=summary
        )
