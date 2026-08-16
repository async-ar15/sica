from agent.memory.working import WorkingMemory


class ContextManager:
    def __init__(self) -> None:
        self.system_prompt = "You are an autonomous self-improving coding agent."

    def build_prompt(self, state: str, memory: WorkingMemory) -> list[dict[str, str]]:
        """Construct the prompt messages for the LLM based on current state and memory."""
        user_content = f"Current State: {state}\\n"
        user_content += memory.to_context_string()

        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content}
        ]
