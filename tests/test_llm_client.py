from __future__ import annotations

import pytest

from src.llm_client import LlmClient, ToolCall, LlmResponse


def test_parse_native_tool_call():
    raw = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "read_file",
                        "arguments": {"path": "/tmp/test.txt"},
                    }
                }
            ],
        }
    }
    response = LlmClient.parse_response(raw)
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].arguments == {"path": "/tmp/test.txt"}
    assert response.text == ""


def test_parse_fallback_xml_tool_call():
    raw = {
        "message": {
            "role": "assistant",
            "content": 'Let me read that file.\n<tool_call>{"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}</tool_call>',
        }
    }
    response = LlmClient.parse_response(raw)
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].arguments == {"path": "/tmp/test.txt"}
    assert "Let me read" in response.text


def test_parse_plain_text():
    raw = {
        "message": {
            "role": "assistant",
            "content": "Here is the answer.",
        }
    }
    response = LlmClient.parse_response(raw)
    assert len(response.tool_calls) == 0
    assert response.text == "Here is the answer."


def test_parse_multiple_fallback_tool_calls():
    raw = {
        "message": {
            "role": "assistant",
            "content": '<tool_call>{"name": "read_file", "arguments": {"path": "a.txt"}}</tool_call>\n<tool_call>{"name": "bash", "arguments": {"command": "ls"}}</tool_call>',
        }
    }
    response = LlmClient.parse_response(raw)
    assert len(response.tool_calls) == 2
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[1].name == "bash"
