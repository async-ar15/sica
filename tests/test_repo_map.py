import textwrap
from pathlib import Path
from typing import Any

from agent.tools.repo_map import RepoMap, Symbol

def test_extract_symbols(tmp_path: Path) -> None:
    test_file = tmp_path / "test_file.py"
    test_file.write_text(textwrap.dedent("""
        def global_func():
            pass
            
        class MyClass:
            def method_one(self):
                pass
                
            async def async_method(self):
                pass
    """), encoding="utf-8")
    
    repo_map = RepoMap(str(tmp_path))
    repo_map.build_map()
    
    symbols = repo_map._map.get("test_file.py")
    assert symbols is not None
    assert len(symbols) == 2
    
    assert symbols[0].name == "global_func"
    assert symbols[0].type == "function"
    assert symbols[0].line_number == 2
    
    assert symbols[1].name == "MyClass"
    assert symbols[1].type == "class"
    assert symbols[1].line_number == 5
    assert len(symbols[1].children) == 2
    
    assert symbols[1].children[0].name == "method_one"
    assert symbols[1].children[0].type == "method"
    
    assert symbols[1].children[1].name == "async_method"
    assert symbols[1].children[1].type == "method"

def test_to_markdown(tmp_path: Path) -> None:
    test_file = tmp_path / "app.py"
    test_file.write_text(textwrap.dedent("""
        class App:
            def run(self):
                pass
    """), encoding="utf-8")
    
    repo_map = RepoMap(str(tmp_path))
    md = repo_map.to_markdown()
    
    assert "📄 `app.py`" in md
    assert "- 📦 `App` *(Line 2)*" in md
    assert "- ⚡ `run` *(Line 3)*" in md

def test_skips_hidden_and_venv(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bad.py").write_text("def x(): pass", encoding="utf-8")
    
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.py").write_text("def y(): pass", encoding="utf-8")
    
    (tmp_path / "good.py").write_text("def good(): pass", encoding="utf-8")
    
    repo_map = RepoMap(str(tmp_path))
    repo_map.build_map()
    
    assert "good.py" in repo_map._map
    assert ".venv/bad.py" not in repo_map._map
    assert ".venv\\bad.py" not in repo_map._map
    assert "__pycache__/cache.py" not in repo_map._map

def test_handles_syntax_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def bad(:", encoding="utf-8")
    
    repo_map = RepoMap(str(tmp_path))
    repo_map.build_map()
    
    # Should safely ignore the file and not crash
    assert "bad.py" not in repo_map._map
