from __future__ import annotations

import asyncio

from src.tools.base import Tool


class BashTool(Tool):
    name = "bash"
    description = "Execute a shell command and return stdout, stderr, and exit code."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 120)"},
        },
        "required": ["command"],
    }

    async def execute(self, **params: object) -> str:
        command = str(params["command"])
        timeout = int(params.get("timeout", 120))
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Command timed out after {timeout}s"
        except OSError as e:
            return f"Error executing command: {e}"
        parts = []
        if stdout:
            parts.append(f"stdout:\n{stdout.decode(errors='replace')}")
        if stderr:
            parts.append(f"stderr:\n{stderr.decode(errors='replace')}")
        parts.append(f"exit_code: {proc.returncode}")
        return "\n".join(parts)
