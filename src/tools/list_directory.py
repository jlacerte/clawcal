from __future__ import annotations

import os

from src.tools.base import Tool


class ListDirectoryTool(Tool):
    name = "list_directory"
    description = "List the contents of a directory."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the directory to list"},
        },
        "required": ["path"],
    }

    async def execute(self, **params: object) -> str:
        path = str(params["path"])
        try:
            entries = sorted(os.listdir(path))
        except OSError as e:
            return f"Error listing directory: {e}"
        lines = []
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                lines.append(f"{entry}/")
            else:
                lines.append(entry)
        return "\n".join(lines) if lines else "(empty directory)"
