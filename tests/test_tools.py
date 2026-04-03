from __future__ import annotations

import pytest

from src.tools.base import Tool


class DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool for testing"
    input_schema = {
        "type": "object",
        "properties": {
            "value": {"type": "string", "description": "A value"},
        },
        "required": ["value"],
    }

    async def execute(self, **params: object) -> str:
        return f"got {params['value']}"


@pytest.mark.asyncio
async def test_dummy_tool_execute():
    tool = DummyTool()
    result = await tool.execute(value="hello")
    assert result == "got hello"


def test_tool_definition():
    tool = DummyTool()
    defn = tool.definition()
    assert defn["type"] == "function"
    assert defn["function"]["name"] == "dummy"
    assert defn["function"]["description"] == "A dummy tool for testing"
    assert "value" in defn["function"]["parameters"]["properties"]


import os
import tempfile

from src.tools.read_file import ReadFileTool
from src.tools.write_file import WriteFileTool
from src.tools.edit_file import EditFileTool
from src.tools.bash import BashTool
from src.tools.glob_tool import GlobTool
from src.tools.grep_tool import GrepTool
from src.tools.list_directory import ListDirectoryTool


@pytest.mark.asyncio
async def test_read_file_full():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line one\nline two\nline three\n")
        path = f.name
    try:
        tool = ReadFileTool()
        result = await tool.execute(path=path)
        assert "1\tline one" in result
        assert "2\tline two" in result
        assert "3\tline three" in result
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_read_file_with_offset_and_limit():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("a\nb\nc\nd\ne\n")
        path = f.name
    try:
        tool = ReadFileTool()
        result = await tool.execute(path=path, offset=2, limit=2)
        assert "2\tb" in result
        assert "3\tc" in result
        assert "1\ta" not in result
        assert "4\td" not in result
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_read_file_not_found():
    tool = ReadFileTool()
    result = await tool.execute(path="/nonexistent/file.txt")
    assert "Error" in result


@pytest.mark.asyncio
async def test_write_file_create():
    path = os.path.join(tempfile.mkdtemp(), "new_file.txt")
    try:
        tool = WriteFileTool()
        result = await tool.execute(path=path, content="hello world")
        assert "Written" in result
        with open(path) as f:
            assert f.read() == "hello world"
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_write_file_overwrite():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("old content")
        path = f.name
    try:
        tool = WriteFileTool()
        await tool.execute(path=path, content="new content")
        with open(path) as f:
            assert f.read() == "new content"
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_edit_file_replace():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello world\ngoodbye world\n")
        path = f.name
    try:
        tool = EditFileTool()
        result = await tool.execute(path=path, old_string="hello world", new_string="hi earth")
        assert "Replaced" in result
        with open(path) as fh:
            content = fh.read()
        assert "hi earth" in content
        assert "goodbye world" in content
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_edit_file_not_found_string():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello world\n")
        path = f.name
    try:
        tool = EditFileTool()
        result = await tool.execute(path=path, old_string="nonexistent", new_string="x")
        assert "not found" in result.lower()
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_bash_echo():
    tool = BashTool()
    result = await tool.execute(command="echo hello")
    assert "hello" in result
    assert "exit_code: 0" in result


@pytest.mark.asyncio
async def test_bash_stderr():
    tool = BashTool()
    result = await tool.execute(command="echo err >&2")
    assert "err" in result


@pytest.mark.asyncio
async def test_bash_timeout():
    tool = BashTool()
    result = await tool.execute(command="sleep 10", timeout=1)
    assert "timed out" in result.lower()


@pytest.mark.asyncio
async def test_glob_tool():
    tmpdir = tempfile.mkdtemp()
    open(os.path.join(tmpdir, "a.txt"), "w").close()
    open(os.path.join(tmpdir, "b.txt"), "w").close()
    open(os.path.join(tmpdir, "c.py"), "w").close()
    tool = GlobTool()
    result = await tool.execute(pattern="*.txt", path=tmpdir)
    assert "a.txt" in result
    assert "b.txt" in result
    assert "c.py" not in result


@pytest.mark.asyncio
async def test_grep_tool():
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "a.txt"), "w") as f:
        f.write("hello world\nfoo bar\nhello again\n")
    with open(os.path.join(tmpdir, "b.txt"), "w") as f:
        f.write("nothing here\n")
    tool = GrepTool()
    result = await tool.execute(pattern="hello", path=tmpdir)
    assert "a.txt" in result
    assert "hello world" in result
    assert "hello again" in result
    assert "b.txt" not in result


@pytest.mark.asyncio
async def test_grep_tool_with_glob_filter():
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, "a.py"), "w") as f:
        f.write("match here\n")
    with open(os.path.join(tmpdir, "a.txt"), "w") as f:
        f.write("match here too\n")
    tool = GrepTool()
    result = await tool.execute(pattern="match", path=tmpdir, glob="*.py")
    assert "a.py" in result
    assert "a.txt" not in result


@pytest.mark.asyncio
async def test_list_directory():
    tmpdir = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmpdir, "subdir"))
    open(os.path.join(tmpdir, "file.txt"), "w").close()
    tool = ListDirectoryTool()
    result = await tool.execute(path=tmpdir)
    assert "subdir/" in result
    assert "file.txt" in result


@pytest.mark.asyncio
async def test_list_directory_not_found():
    tool = ListDirectoryTool()
    result = await tool.execute(path="/nonexistent/dir")
    assert "Error" in result


@pytest.mark.asyncio
async def test_grep_skips_excluded_directories(tmp_path):
    """grep_tool should skip .git, .venv, node_modules, __pycache__."""
    from src.tools.grep_tool import GrepTool

    # Create files in excluded directories
    for excluded in [".git", ".venv", "node_modules", "__pycache__"]:
        d = tmp_path / excluded
        d.mkdir()
        (d / "match.py").write_text("findme_secret_pattern")

    # Create a file in a normal directory
    (tmp_path / "normal.py").write_text("findme_secret_pattern")

    tool = GrepTool()
    result = await tool.execute(pattern="findme_secret_pattern", path=str(tmp_path))
    assert "normal.py" in result
    assert ".git" not in result
    assert ".venv" not in result
    assert "node_modules" not in result
    assert "__pycache__" not in result
