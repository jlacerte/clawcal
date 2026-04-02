from __future__ import annotations

from src.tools.base import Tool


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a file and return its contents with line numbers."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read"},
            "offset": {"type": "integer", "description": "Line number to start reading from (1-based)"},
            "limit": {"type": "integer", "description": "Maximum number of lines to read"},
        },
        "required": ["path"],
    }

    async def execute(self, **params: object) -> str:
        path = str(params["path"])
        offset = int(params.get("offset", 1))
        limit = params.get("limit")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            return f"Error reading file: {e}"
        start = max(offset - 1, 0)
        end = start + int(limit) if limit is not None else len(lines)
        selected = lines[start:end]
        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            numbered.append(f"{i}\t{line.rstrip()}")
        return "\n".join(numbered)
