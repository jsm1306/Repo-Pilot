from dataclasses import dataclass
import ast

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    symbol: str | None = None
    symbol_type: str | None = None


class StructuralChunker:
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }

    def __init__(self):
        self.parsers = {
            "python": self._create_parser(tree_sitter_python.language()),
            "javascript": self._create_parser(tree_sitter_javascript.language()),
            "typescript": self._create_parser(tree_sitter_typescript.language_typescript()),
            "tsx": self._create_parser(tree_sitter_typescript.language_tsx()),
        }

    def _create_parser(self, language):
        parser = Parser()
        parser.language = Language(language)
        return parser

    def chunk_file(self, file_path, content):
        extension = "." + file_path.split(".")[-1].lower()
        language = self.LANGUAGE_MAP.get(extension)

        if language not in self.parsers:
            return self._fallback_chunks(file_path, content, language or "unknown")

        if language == "python":
            return self._python_chunks(file_path, content)

        return self._tree_sitter_chunks(file_path, content, language)

    def _python_chunks(self, file_path, content):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._fallback_chunks(file_path, content, "python")

        lines = content.splitlines()
        chunks = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                chunks.append(CodeChunk(
                    file_path=file_path,
                    content="\n".join(lines[start - 1:end]),
                    start_line=start,
                    end_line=end,
                    language="python",
                    symbol=node.name,
                    symbol_type="class" if isinstance(node, ast.ClassDef) else "function"
                ))

        return chunks or self._fallback_chunks(file_path, content, "python")

    def _tree_sitter_chunks(self, file_path, content, language):
        parser = self.parsers[language]
        tree = parser.parse(content.encode("utf-8"))
        lines = content.splitlines()
        chunks = []

        symbol_types = {
            "function_declaration": "function",
            "function_definition": "function",
            "method_definition": "method",
            "class_declaration": "class",
            "class_definition": "class",
            "arrow_function": "function",
        }

        def visit(node):
            if node.type in symbol_types:
                start = node.start_point[0] + 1
                end = node.end_point[0] + 1
                symbol = self._get_symbol_name(node, content)

                chunks.append(CodeChunk(
                    file_path=file_path,
                    content="\n".join(lines[start - 1:end]),
                    start_line=start,
                    end_line=end,
                    language=language,
                    symbol=symbol,
                    symbol_type=symbol_types[node.type]
                ))

            for child in node.children:
                visit(child)

        visit(tree.root_node)

        return chunks or self._fallback_chunks(file_path, content, language)

    def _get_symbol_name(self, node, content):
        for child in node.children:
            if child.type in {"identifier", "property_identifier"}:
                return content.encode("utf-8")[child.start_byte:child.end_byte].decode("utf-8")

        return None

    def _fallback_chunks(self, file_path, content, language, chunk_size=50, overlap=10):
        lines = content.splitlines()
        chunks = []
        start = 0

        while start < len(lines):
            end = min(start + chunk_size, len(lines))
            chunks.append(CodeChunk(
                file_path=file_path,
                content="\n".join(lines[start:end]),
                start_line=start + 1,
                end_line=end,
                language=language
            ))
            start += chunk_size - overlap

        return chunks