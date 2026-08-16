
from agent.tools.aci import AgentMode

PERMISSION_MATRIX = {
    AgentMode.PLAN: {"view_file", "find_in_repo", "run_tests", "remember"},
    AgentMode.BUILD: {
        "view_file",
        "find_in_repo",
        "edit_file",
        "create_file",
        "run_command",
        "run_tests",
        "remember",
    },
    AgentMode.REVIEW: {"view_file", "find_in_repo", "run_tests", "remember"},
}

def check_permission(tool_name: str, mode: AgentMode) -> bool:
    """Check if a tool is allowed in a given mode."""
    allowed_tools = PERMISSION_MATRIX.get(mode, set())
    return tool_name in allowed_tools
