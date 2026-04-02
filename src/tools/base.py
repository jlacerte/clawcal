from __future__ import annotations

from abc import ABC, abstractmethod


class Tool(ABC):
    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def execute(self, **params: object) -> str: ...

    def definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
