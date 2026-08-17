import logging

from agent.memory.failure import FailureRecord
from agent.memory.working import WorkingMemory
from agent.tools.fault_localizer import EditLocation

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self, max_tokens: int = 128000, model: str = "gemini-2.5-pro") -> None:
        self.system_prompt = "You are an autonomous self-improving coding agent."
        self.max_tokens = max_tokens
        self.model = model

    def _estimate_tokens(self, text: str) -> int:
        # Simple approximation: ~4 characters per token
        return len(text) // 4

    def build_prompt(
        self,
        state: str,
        memory: WorkingMemory,
        failures: list[FailureRecord] | None = None,
        repo_map: str = "",
        fault_locations: list[EditLocation] | None = None,
        raw_logs: str = ""
    ) -> list[dict[str, str]]:
        """Construct the prompt messages for the LLM based on current state and memory, applying 6-layer context compaction if necessary."""

        failures = failures or []
        fault_locations = fault_locations or []

        # Layer 1: System prompt & Goals
        l1_system = self.system_prompt
        l1_goal = f"Goal: {memory.current_goal}\nCurrent State: {state}\n"

        # Layer 2: Repo Map
        l2_repo = f"Repo Map:\n{repo_map}\n" if repo_map else ""

        # Layer 3: Fault Locations
        l3_faults = "Fault Locations:\n" + "\n".join(str(loc) for loc in fault_locations) + "\n" if fault_locations else ""

        # Layer 4: Retrieved Failures
        l4_failures = "Related Past Failures:\n"
        for f in failures:
            l4_failures += f"- Error: {f.error_signature}\n  Hypothesis: {f.hypothesis}\n  Result: {f.result}\n"
        if not failures:
            l4_failures = ""

        # Layer 5: Working Memory Snapshot
        l5_memory = f"Working Memory:\n{memory.to_context_string()}\n"

        # Layer 6: Raw logs
        l6_logs = f"Terminal Output / Logs:\n{raw_logs}\n" if raw_logs else ""

        # Calculate tokens
        t1 = self._estimate_tokens(l1_system + l1_goal)
        t2 = self._estimate_tokens(l2_repo)
        t3 = self._estimate_tokens(l3_faults)
        t4 = self._estimate_tokens(l4_failures)
        t5 = self._estimate_tokens(l5_memory)
        t6 = self._estimate_tokens(l6_logs)

        total_tokens = t1 + t2 + t3 + t4 + t5 + t6
        threshold = int(self.max_tokens * 0.6)

        if total_tokens > threshold:
            logger.info(f"Context size ({total_tokens}) exceeds 60% threshold ({threshold}). Compacting...")

            # Compact Layer 6: Raw logs (Truncate to last 1000 chars)
            if t6 > 0:
                l6_logs = f"Terminal Output (Truncated):\n...{raw_logs[-1000:]}\n"
                total_tokens = t1 + t2 + t3 + t4 + t5 + self._estimate_tokens(l6_logs)

            # Compact Layer 5 if still over limit
            if total_tokens > threshold and t5 > 0:
                l5_memory = "Working Memory (Compacted):\n"
                l5_memory += f"Tried Hypotheses: {', '.join(memory.tried_hypotheses)}\n"
                if memory.last_error:
                    l5_memory += f"Last Error: {memory.last_error[:500]}...\n"
                total_tokens = t1 + t2 + t3 + t4 + self._estimate_tokens(l5_memory) + self._estimate_tokens(l6_logs)

            # Compact Layer 2 if still over limit
            if total_tokens > threshold and t2 > 0:
                # Keep paths but remove function signatures or extra details if possible
                # Since repo_map is just a string, we might just truncate it or keep only top-level dirs
                lines = repo_map.splitlines()
                compacted_lines = [line for line in lines if not line.startswith("  ")] # keep shallow items
                l2_repo = "Repo Map (Compacted):\n" + "\n".join(compacted_lines) + "\n"

        user_content = l1_goal + l2_repo + l3_faults + l4_failures + l5_memory + l6_logs

        return [
            {"role": "system", "content": l1_system},
            {"role": "user", "content": user_content}
        ]
