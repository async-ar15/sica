import ast
import os
from pathlib import Path

from pydantic import BaseModel, Field


class Symbol(BaseModel):
    name: str
    type: str
    line_number: int
    children: list["Symbol"] = Field(default_factory=list)


class RepoMap:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = Path(repo_path)
        self._map: dict[str, list[Symbol]] = {}

    def build_map(self) -> dict[str, list[Symbol]]:
        self._map = {}
        for root, dirs, files in os.walk(self.repo_path):
            # Skip common hidden and environment directories
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in ("__pycache__", "venv", ".venv", "env")
            ]

            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    try:
                        relative_path = file_path.relative_to(self.repo_path)
                        symbols = self._parse_file(file_path)
                        if symbols:
                            self._map[str(relative_path).replace("\\", "/")] = symbols
                    except Exception:
                        pass # Ignore parsing errors on individual files
        return self._map

    def _parse_file(self, file_path: Path) -> list[Symbol]:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        return self._extract_symbols(tree.body)

    def _extract_symbols(self, nodes: list[ast.stmt]) -> list[Symbol]:
        symbols = []
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                children = self._extract_symbols(node.body)
                # Change method types
                for child in children:
                    if child.type == "function":
                        child.type = "method"

                symbols.append(Symbol(
                    name=node.name,
                    type="class",
                    line_number=node.lineno,
                    children=children
                ))
            elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                symbols.append(Symbol(
                    name=node.name,
                    type="function",
                    line_number=node.lineno
                ))
        return symbols

    def to_markdown(self) -> str:
        if not self._map:
            self.build_map()

        lines = []
        # Sort files alphabetically for deterministic output
        for file_path in sorted(self._map.keys()):
            symbols = self._map[file_path]
            lines.append(f"📄 `{file_path}`")
            for symbol in symbols:
                self._format_symbol(symbol, lines, level=1)
            lines.append("")
        return "\n".join(lines).strip()

    def _format_symbol(self, symbol: Symbol, lines: list[str], level: int) -> None:
        indent = "  " * level
        icon = "📦" if symbol.type == "class" else "⚡"
        lines.append(f"{indent}- {icon} `{symbol.name}` *(Line {symbol.line_number})*")
        for child in symbol.children:
            self._format_symbol(child, lines, level + 1)
