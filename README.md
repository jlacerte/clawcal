# Clawcal

Local coding agent MCP server powered by Ollama.

Clawcal combines a local LLM (Qwen 3 14B, Llama, etc.) with 7 coding tools and an agentic loop, all exposed as a [Model Context Protocol](https://modelcontextprotocol.io/) server. Any MCP client (Claude Desktop, VS Code, etc.) can use your local AI to read, write, edit, search, and execute code autonomously.

## Features

- **7 coding tools** — `read_file`, `write_file`, `edit_file`, `bash`, `glob_tool`, `grep_tool`, `list_directory`
- **Composite `code_agent` tool** — send a natural language task, the local LLM orchestrates the tools to complete it
- **Hybrid tool calling** — native function calling + XML fallback for smaller models
- **MCP stdio transport** — plug into any MCP-compatible client
- **Zero cloud dependency** — everything runs on your machine

## Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com/) installed and running

### Install

```bash
# Pull a model
ollama pull qwen3:14b

# Clone and install
git clone https://github.com/jlacerte/clawcal.git
cd clawcal
pip install -e .
```

### Run

```bash
# Start Ollama (if not already running)
ollama serve

# Launch the MCP server
python -m src.server --model qwen3:14b
```

### Configure Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "clawcal": {
      "command": "python",
      "args": ["-m", "src.server", "--model", "qwen3:14b"],
      "cwd": "/path/to/clawcal"
    }
  }
}
```

## Architecture

```
MCP Client (Claude Desktop, VS Code, etc.)
    |
    v (stdio / MCP protocol)
+------------------------------------------+
|  server.py — MCP Server                  |
|                                          |
|  Exposes:                                |
|  +-- 7 raw coding tools                 |
|  +-- code_agent (composite tool)         |
|          |                               |
|          v                               |
|  +-------------------+                   |
|  | agent.py          |<------+           |
|  | Agentic loop      |       |           |
|  | prompt->tool->rep |       |           |
|  +--------+----------+       |           |
|           |            result|           |
|           v                  |           |
|  +----------------+          |           |
|  | tool_registry  |----------+           |
|  | 7 tools        |                      |
|  +----------------+                      |
|           |                              |
|           v                              |
|  +----------------+                      |
|  | llm_client.py  |---- HTTP --- Ollama  |
|  | hybrid parse   |   (localhost:11434)  |
|  +----------------+                      |
+------------------------------------------+
```

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line numbers |
| `write_file` | Write/create files with auto directory creation |
| `edit_file` | Search and replace in files |
| `bash` | Execute shell commands with timeout |
| `glob_tool` | Find files by glob pattern |
| `grep_tool` | Search file contents with regex |
| `list_directory` | List directory contents |
| `code_agent` | Orchestrate all tools via local LLM to complete coding tasks |

## Development

```bash
# Run tests
python -m pytest -v

# Run a specific test
python -m pytest tests/test_agent.py -v
```

## License

MIT
