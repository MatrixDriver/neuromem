"""Callback LLM provider that delegates LLM calls to MCP Host."""
from __future__ import annotations

from neuromem.providers.llm import LLMProvider


class LLMCallbackRequired(Exception):
    """Raised when LLM call needs to be executed by MCP Host.

    The MCP server catches this exception, returns the prompt to the
    MCP Host (e.g. Claude Code), and the Host executes it with its own LLM.
    """

    def __init__(self, messages: list[dict], temperature: float, max_tokens: int):
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        super().__init__("LLM callback required")


class CallbackLLM(LLMProvider):
    """LLM provider that raises LLMCallbackRequired instead of calling an API.

    Used in mcp_host mode: the MCP server catches the exception,
    returns the prompt to the MCP Host, and the Host executes it
    with its own LLM.
    """

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        raise LLMCallbackRequired(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
