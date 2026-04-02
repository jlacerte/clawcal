from __future__ import annotations

import fnmatch
import os
import re

from src.tools.base import Tool


class GrepTool(Tool):
    name = "grep_tool"
    description = "Search file contents for a regex pattern."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory to search in (default: cwd)"},
            "glob": {"type": "string", "description": "File glob filter (e.g. '*.py')"},
        },
        "required": ["pattern"],
    }

    async def execute(self, **params: object) -> str:
        pattern = str(params["pattern"])
        path = str(params.get("path", "."))
        glob_filter = params.get("glob")
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regex: {e}"
        results: list[str] = []
        for root, _dirs, files in os.walk(path):
            for fname in sorted(files):
                if glob_filter and not fnmatch.fnmatch(fname, str(glob_filter)):
                    continue
                filepath = os.path.join(root, fname)
                try:
                    with open(filepath, encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{filepath}:{lineno}:{line.rstrip()}")
                except OSError:
                    continue
        if not results:
            return "No matches found."
        return "\n".join(results)
