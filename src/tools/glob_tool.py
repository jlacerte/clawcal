from __future__ import annotations

import glob as globlib
import os

from src.tools.base import Tool


class GlobTool(Tool):
    name = "glob_tool"
    description = "Find files matching a glob pattern."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
            "path": {"type": "string", "description": "Directory to search in (default: cwd)"},
        },
        "required": ["pattern"],
    }

    async def execute(self, **params: object) -> str:
        pattern = str(params["pattern"])
        path = str(params.get("path", "."))
        full_pattern = os.path.join(path, pattern)
        matches = sorted(globlib.glob(full_pattern, recursive=True))
        if not matches:
            return "No files matched."
        return "\n".join(matches)
