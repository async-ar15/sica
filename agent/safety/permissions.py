from agent.tools.aci import AgentMode


class PermissionGate:
    """Controls which tools the agent can execute based on its current mode."""

    PERMISSION_MATRIX: dict[str, dict[AgentMode, bool]] = {
        "view_file":    {AgentMode.PLAN: True,  AgentMode.BUILD: True,  AgentMode.REVIEW: True},
        "find_in_repo": {AgentMode.PLAN: True,  AgentMode.BUILD: True,  AgentMode.REVIEW: True},
        "edit_file":    {AgentMode.PLAN: False, AgentMode.BUILD: True,  AgentMode.REVIEW: False},
        "create_file":  {AgentMode.PLAN: False, AgentMode.BUILD: True,  AgentMode.REVIEW: False},
        "run_command":  {AgentMode.PLAN: False, AgentMode.BUILD: True,  AgentMode.REVIEW: False},
        "run_tests":    {AgentMode.PLAN: True,  AgentMode.BUILD: True,  AgentMode.REVIEW: True},
        "remember":     {AgentMode.PLAN: True,  AgentMode.BUILD: True,  AgentMode.REVIEW: True},
    }

    def __init__(self, default_mode: AgentMode = AgentMode.PLAN) -> None:
        self._current_mode = default_mode
        # In the future, log initial mode to trajectory

    def check(self, tool_name: str, mode: AgentMode | None = None) -> bool:
        """Check if a tool is allowed in the specified mode (or current mode)."""
        active_mode = mode if mode is not None else self._current_mode

        if tool_name not in self.PERMISSION_MATRIX:
            return False  # Deny by default

        return self.PERMISSION_MATRIX[tool_name].get(active_mode, False)

    def switch_mode(self, new_mode: AgentMode) -> None:
        """Switch the current permission mode."""
        self._current_mode = new_mode
        # In the future, log mode switch to trajectory

    def allow_in_build_only(self, tool_name: str) -> None:
        """Register a dynamic tool to be allowed only in BUILD mode."""
        self.PERMISSION_MATRIX[tool_name] = {
            AgentMode.PLAN: False,
            AgentMode.BUILD: True,
            AgentMode.REVIEW: False
        }

    @property
    def current_mode(self) -> AgentMode:
        return self._current_mode
