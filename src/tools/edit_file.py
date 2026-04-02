from __future__ import annotations

from src.tools.base import Tool


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace an exact string in a file with a new string."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to edit"},
            "old_string": {"type": "string", "description": "Exact string to find and replace"},
            "new_string": {"type": "string", "description": "String to replace with"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    async def execute(self, **params: object) -> str:
        path = str(params["path"])
        old_string = str(params["old_string"])
        new_string = str(params["new_string"])
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            return f"Error reading file: {e}"
        if old_string not in content:
            return f"Error: old_string not found in {path}"
        count = content.count(old_string)
        new_content = content.replace(old_string, new_string, 1)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except OSError as e:
            return f"Error writing file: {e}"
        return f"Replaced 1 occurrence in {path}" + (
            f" (warning: {count - 1} more occurrences remain)" if count > 1 else ""
        )
