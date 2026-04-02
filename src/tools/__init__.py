from __future__ import annotations

from src.tools.bash import BashTool
from src.tools.edit_file import EditFileTool
from src.tools.glob_tool import GlobTool
from src.tools.grep_tool import GrepTool
from src.tools.list_directory import ListDirectoryTool
from src.tools.read_file import ReadFileTool
from src.tools.write_file import WriteFileTool

ALL_TOOLS = [
    ReadFileTool(),
    WriteFileTool(),
    EditFileTool(),
    BashTool(),
    GlobTool(),
    GrepTool(),
    ListDirectoryTool(),
]
