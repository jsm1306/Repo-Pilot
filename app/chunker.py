from dataclasses import dataclass


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str 
    symbol: str | None = None
    symbol_type: str | None = None


class CodeChunker:
    LANGUAGE_MAP={
        ".py":"python",
        ".js":"javascript",
        ".jsx":"javascript",
        ".ts":"typescript",
        ".tsx":"typescript",
        ".java":"java",
        ".cpp":"cpp",
        ".c":"c",
        ".go":"go",
        ".rs":"rust",
        ".php":"php",
        ".rb":"ruby",
        ".html":"html",
        ".css":"css",
    }
    def __init__(self, chunk_size=50, overlap=10):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_file(self, file_path: str, content: str):
        
        lines = content.splitlines()
        chunks = []
        start = 0
        language=self.LANGUAGE_MAP.get("." + file_path.split(".")[-1].lower(),"unknown")
        while start < len(lines):
            end = min(start + self.chunk_size,len(lines))
            chunk_content = "\n".join(lines[start:end])
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    content=chunk_content,
                    start_line=start + 1,
                    end_line=end,
                    language=language
                )
            )
            start += self.chunk_size - self.overlap

        return chunks