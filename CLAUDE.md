# CLAUDE.md

## Project
Clawcal — Local coding agent MCP server powered by Ollama (Qwen 3 14B).
Python monolith: MCP server (stdio) + agentic loop + hybrid tool call parsing.

## Stack
- Python 3.12+, mcp SDK, httpx, pydantic
- Target platform: macOS

## Verification
```bash
python -m pytest -v
```

## Structure
- `src/` — main source (server, agent, llm_client, tool_registry, tools/)
- `tests/` — pytest tests
- One file per tool in `src/tools/`

## Conventions
- Commits: conventional (`feat:`, `test:`, `fix:`, `docs:`)
- TDD: write failing test first, then implement
- async/await throughout
