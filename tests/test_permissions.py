from agent.safety.permissions import PermissionGate
from agent.tools.aci import AgentMode


def test_plan_mode_allows_view_file():
    gate = PermissionGate(default_mode=AgentMode.PLAN)
    assert gate.check("view_file") is True

def test_plan_mode_blocks_edit_file():
    gate = PermissionGate(default_mode=AgentMode.PLAN)
    assert gate.check("edit_file") is False

def test_plan_mode_blocks_create_file():
    gate = PermissionGate(default_mode=AgentMode.PLAN)
    assert gate.check("create_file") is False

def test_plan_mode_blocks_run_command():
    gate = PermissionGate(default_mode=AgentMode.PLAN)
    assert gate.check("run_command") is False

def test_plan_mode_allows_run_tests():
    gate = PermissionGate(default_mode=AgentMode.PLAN)
    assert gate.check("run_tests") is True

def test_build_mode_allows_all():
    gate = PermissionGate(default_mode=AgentMode.BUILD)
    tools = ["view_file", "find_in_repo", "edit_file", "create_file", "run_command", "run_tests", "remember"]
    for t in tools:
        assert gate.check(t) is True

def test_review_mode_blocks_edit_file():
    gate = PermissionGate(default_mode=AgentMode.REVIEW)
    assert gate.check("edit_file") is False

def test_review_mode_allows_view_file():
    gate = PermissionGate(default_mode=AgentMode.REVIEW)
    assert gate.check("view_file") is True

def test_unknown_tool_denied():
    gate = PermissionGate(default_mode=AgentMode.BUILD)
    assert gate.check("unknown_tool_that_does_not_exist") is False

def test_switch_mode_changes_behavior():
    gate = PermissionGate(default_mode=AgentMode.PLAN)
    assert gate.check("edit_file") is False
    gate.switch_mode(AgentMode.BUILD)
    assert gate.check("edit_file") is True

def test_default_mode_is_plan():
    gate = PermissionGate()
    assert gate.current_mode == AgentMode.PLAN
