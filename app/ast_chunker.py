import ast
from dataclasses import dataclass

@dataclass
class ASTChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int
    symbol: str
    symbol_type: str
    language: str = "python"

class PythonASTChunker:
    def chunk_file(self, file_path: str, content: str):
        tree = ast.parse(content)
        lines = content.splitlines()
        chunks = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                end = getattr(node, "end_lineno", start)
                chunk_content = "\n".join(lines[start - 1:end])

                symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"

                chunks.append(ASTChunk(
                    file_path=file_path,
                    content=chunk_content,
                    start_line=start,
                    end_line=end,
                    symbol=node.name,
                    symbol_type=symbol_type
                ))

        return chunks