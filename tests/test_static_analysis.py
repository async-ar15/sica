import pytest

from agent.safety.static_analysis import StaticAnalyzer


def test_parse_ruff_json():
    analyzer = StaticAnalyzer(sandbox=None)  # type: ignore[arg-type]
    output = '[{"filename": "test.py", "location": {"row": 1, "column": 2}, "code": "E501", "message": "Line too long", "fix": null}]'
    errors, fixable = analyzer._parse_ruff_json(output)
    assert len(errors) == 1
    assert errors[0].file == "test.py"
    assert errors[0].line == 1
    assert errors[0].column == 2
    assert errors[0].code == "E501"
    assert errors[0].message == "Line too long"
    assert fixable == 0

def test_parse_mypy_output():
    analyzer = StaticAnalyzer(sandbox=None)  # type: ignore[arg-type]
    output = 'test.py:1: error: Missing type annotation [no-untyped-def]\nSuccess: no issues found'
    errors = analyzer._parse_mypy_output(output)
    assert len(errors) == 1
    assert errors[0].file == "test.py"
    assert errors[0].line == 1
    assert errors[0].code == "no-untyped-def"
    assert errors[0].message == "Missing type annotation"
    assert errors[0].tool == "mypy"

def test_parse_bandit_json():
    analyzer = StaticAnalyzer(sandbox=None)  # type: ignore[arg-type]
    output = '{"results": [{"filename": "test.py", "line_number": 5, "test_id": "B101", "issue_text": "Use of assert detected", "issue_severity": "LOW"}]}'
    errors = analyzer._parse_bandit_json(output)
    assert len(errors) == 1
    assert errors[0].file == "test.py"
    assert errors[0].line == 5
    assert errors[0].code == "B101"
    assert errors[0].message == "Use of assert detected"
    assert errors[0].severity == "low"
    assert errors[0].tool == "bandit"

def test_empty_file_list_no_crash():
    analyzer = StaticAnalyzer(sandbox=None)  # type: ignore[arg-type]
    # The analyze method expects a list of files but is async so we just test the parsing methods for resilience
    assert analyzer._parse_ruff_json("") == ([], 0)
    assert analyzer._parse_mypy_output("") == []
    assert analyzer._parse_bandit_json("") == []

from unittest.mock import AsyncMock, Mock


@pytest.mark.asyncio
async def test_analyze_clean_code_returns_zero_errors():
    sandbox_mock = AsyncMock()
    # Mock successful execution returning empty JSON/success strings
    res_ruff = Mock(stdout='[]', returncode=0)
    res_mypy = Mock(stdout='Success: no issues found in 1 source file\n', returncode=0)
    res_bandit = Mock(stdout='{"results": []}', returncode=0)
    sandbox_mock.execute.side_effect = [res_ruff, res_mypy, res_bandit]

    analyzer = StaticAnalyzer(sandbox=sandbox_mock)  # type: ignore[arg-type]
    result = await analyzer.analyze(["test.py"])

    assert result.errors == 0
    assert result.security_issues == 0
    assert len(result.details) == 0

@pytest.mark.asyncio
async def test_analyze_syntax_error_detected():
    sandbox_mock = AsyncMock()
    res_ruff = Mock(stdout='[{"filename": "test.py", "location": {"row": 1, "column": 1}, "code": "E999", "message": "SyntaxError", "fix": null}]', returncode=1)
    res_mypy = Mock(stdout='Success', returncode=0)
    res_bandit = Mock(stdout='{"results": []}', returncode=0)
    sandbox_mock.execute.side_effect = [res_ruff, res_mypy, res_bandit]

    analyzer = StaticAnalyzer(sandbox=sandbox_mock)  # type: ignore[arg-type]
    result = await analyzer.analyze(["test.py"])

    assert result.errors == 1
    assert len(result.details) == 1
    assert result.details[0].code == "E999"

@pytest.mark.asyncio
async def test_analyze_type_error_detected():
    sandbox_mock = AsyncMock()
    res_ruff = Mock(stdout='[]', returncode=0)
    res_mypy = Mock(stdout='test.py:1: error: Type error [type-err]', returncode=1)
    res_bandit = Mock(stdout='{"results": []}', returncode=0)
    sandbox_mock.execute.side_effect = [res_ruff, res_mypy, res_bandit]

    analyzer = StaticAnalyzer(sandbox=sandbox_mock)  # type: ignore[arg-type]
    result = await analyzer.analyze(["test.py"])

    assert result.errors == 1
    assert len(result.details) == 1
    assert result.details[0].tool == "mypy"

@pytest.mark.asyncio
async def test_auto_fix_lint_modifies_files():
    sandbox_mock = AsyncMock()
    sandbox_mock.execute.return_value = Mock(returncode=0)

    analyzer = StaticAnalyzer(sandbox=sandbox_mock)  # type: ignore[arg-type]
    result = await analyzer.auto_fix_lint(["test.py"])
    assert result == ["test.py"]
