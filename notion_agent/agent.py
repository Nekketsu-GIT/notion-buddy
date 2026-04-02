"""NotionAgent: Claude claude-sonnet-4-6 + MCP tool loop (max 10 iterations)."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import anthropic
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from notion_agent.models import AgentResult

SYSTEM_PROMPT = (
    "You are a Notion workspace intelligence agent. You have access to tools that let\n"
    "you search, read, and write to a Notion workspace.\n"
    "\n"
    "When given a task:\n"
    "1. Start by searching the workspace to understand what content exists\n"
    "2. Fetch full details of the most relevant pages\n"
    "3. Reason step-by-step before taking write actions\n"
    "4. When creating audit reports or summaries, create them as Notion pages so the\n"
    "   user has a persistent record\n"
    "5. Always include page URLs in your final answer so the user can navigate directly\n"
    "\n"
    "Be concise in your reasoning. Prefer action over explanation."
)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_ITERATIONS = 10


def _first_text(blocks: list[Any], reverse: bool = False) -> str:
    """Return the first non-empty text from a list of response content blocks."""
    iterator: Any = reversed(blocks) if reverse else iter(blocks)
    for block in iterator:
        if hasattr(block, "text") and block.text:
            return block.text
    return ""


class NotionAgent:
    def run(self, prompt: str, verbose: bool = True) -> AgentResult:
        return asyncio.run(self._run_async(prompt, verbose))

    async def _run_async(self, prompt: str, verbose: bool) -> AgentResult:
        start = time.monotonic()

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "notion_agent", "serve"],
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                anthropic_tools = [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": t.inputSchema,
                    }
                    for t in tools_result.tools
                ]

                client = anthropic.AsyncAnthropic()
                messages: list[dict] = [{"role": "user", "content": prompt}]
                actions_taken: list[str] = []
                pages_created: list[str] = []
                iterations = 0
                response = None

                async def _call_tool(tool_call: Any) -> dict:
                    action = f"{tool_call.name}({json.dumps(tool_call.input)})"
                    actions_taken.append(action)
                    if verbose:
                        print(f"\n[tool] {action}", flush=True)
                    try:
                        result = await session.call_tool(tool_call.name, tool_call.input)
                        result_text = result.content[0].text if result.content else "{}"
                        if tool_call.name == "create_page":
                            try:
                                data = json.loads(result_text)
                                if url := data.get("url"):
                                    pages_created.append(url)
                            except (json.JSONDecodeError, AttributeError):
                                pass
                        if verbose:
                            print(f"[result] {result_text[:200]}", flush=True)
                        return {
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": result_text,
                        }
                    except Exception as exc:
                        return {
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": json.dumps({"error": str(exc)}),
                            "is_error": True,
                        }

                while iterations < MAX_ITERATIONS:
                    iterations += 1

                    response = await client.messages.create(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        system=SYSTEM_PROMPT,
                        tools=anthropic_tools,
                        messages=messages,
                    )

                    messages.append({"role": "assistant", "content": response.content})

                    if verbose:
                        for block in response.content:
                            if hasattr(block, "text") and block.text:
                                print(block.text, flush=True)

                    if response.stop_reason == "end_turn":
                        break

                    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
                    if not tool_use_blocks:
                        break

                    tool_results = await asyncio.gather(*[_call_tool(tc) for tc in tool_use_blocks])
                    messages.append({"role": "user", "content": list(tool_results)})

                return AgentResult(
                    final_answer=_first_text(response.content, reverse=True) if response else "",
                    actions_taken=actions_taken,
                    pages_created=pages_created,
                    duration_seconds=time.monotonic() - start,
                    iterations=iterations,
                )
