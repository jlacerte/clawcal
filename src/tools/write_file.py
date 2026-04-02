from __future__ import annotations

import os

from src.tools.base import Tool


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file. Creates parent directories if needed."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, **params: object) -> str:
        path = str(params["path"])
        content = str(params["content"])
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written {len(content)} bytes to {path}"
        except OSError as e:
            return f"Error writing file: {e}"
