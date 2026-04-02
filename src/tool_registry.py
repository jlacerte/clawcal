from __future__ import annotations

from src.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict]:
        return [tool.definition() for tool in self._tools.values()]

    def get_tool(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    async def execute(self, name: str, params: dict) -> str:
        tool = self.get_tool(name)
        return await tool.execute(**params)

    def names(self) -> list[str]:
        return list(self._tools.keys())
