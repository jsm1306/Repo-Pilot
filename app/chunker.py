from dataclasses import dataclass


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int


class CodeChunker:
    def __init__(self, chunk_size: int = 50, overlap: int = 10):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_file(self, file_path: str, content: str):
        lines = content.splitlines()
        chunks = []
        start = 0
        while start < len(lines):
            end = min(start + self.chunk_size,len(lines))
            chunk_content = "\n".join(lines[start:end])
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    content=chunk_content,
                    start_line=start + 1,
                    end_line=end,
                )
            )
            start += self.chunk_size - self.overlap

        return chunks