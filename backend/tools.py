
"""MCP client, our own MCP file server and the LangChain tool wrappers.

This file plays two roles:
  * imported by the app: the MCP client (MCPToolbox) and the tools the agents use
  * run as a script, `python tools.py <sandbox_dir>`: our own tiny MCP file server over
    stdio. config.build_mcp_config() starts it, so no Node/npx is needed (Vercel has none).

Keep print() out of this file: stdout is the MCP stdio channel while it runs as a server.
"""


import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server import MCPServer
from langchain.mcp import MCPAdapter  # beta API, as used in the original notebook
from langchain_core.tools import tool

# This module is imported as ``backend.tools`` by the app, but it is also
# launched directly as a small stdio MCP server. Support both execution modes.
if __package__:
    from .config import (
        TOOL_AIRPORTS,
        TOOL_FLIGHTS,
        TOOL_FS_WRITE,
        TOOL_TAVILY_SEARCH,
        build_mcp_config,
    )
else:
    from config import (
        TOOL_AIRPORTS,
        TOOL_FLIGHTS,
        TOOL_FS_WRITE,
        TOOL_TAVILY_SEARCH,
        build_mcp_config,
    )


# ------------------- Our own MCP file server
# Agents see it as `tripfiles_write_file` (server name + tool name).
file_mcp = MCPServer("tripfiles")


def _sandbox() -> Path:
    arg = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TRIP_PLANNER_SANDBOX", "travel_plan_file")
    return Path(arg).resolve()


@file_mcp.tool()
def write_file(filename: str, content: str) -> str:
    """Write text content to a .txt file inside the sandbox directory.

    Args:
        filename: Name of the file, for example lisbon_portugal.txt (must end in .txt).
        content: The full text to write.
    """
    sandbox = _sandbox()
    path = (sandbox / filename).resolve()

    # Safety: no ../ or absolute paths that escape the sandbox, and only .txt files
    if not path.is_relative_to(sandbox):
        raise ValueError("File must be written inside the sandbox directory.")
    if path.suffix != ".txt":
        raise ValueError("Only .txt files can be written.")

    sandbox.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Saved {len(content)} characters to {path}"


# ---------------------------------------------------------------- MCP connection
class MCPToolbox:
    """Opens the MCP connections and hands out tools by name.

    The connections live inside one long-running task, so they are opened and
    closed by the same task (required by anyio). Two ways to use it:
      * persistent: call get_tools()/get_tool() and close() once at the very end
        (notebook, Streamlit, Docker)
      * per request: wrap each request in `async with toolbox.session():`; the
        connections close when the last overlapping request leaves (serverless)
    """

    def __init__(self, config_factory):
        self._config_factory = config_factory
        self._tools = None
        self._task: asyncio.Task | None = None
        self._ready: asyncio.Event | None = None
        self._stop: asyncio.Event | None = None
        self._error: Exception | None = None
        self._lock_obj: asyncio.Lock | None = None
        self._users = 0

    def _lock(self) -> asyncio.Lock:
        if self._lock_obj is None:
            self._lock_obj = asyncio.Lock()
        return self._lock_obj

    async def _run(self):
        try:
            async with MCPAdapter(self._config_factory()) as adapter:
                self._tools = await adapter.list_tools()
                self._ready.set()
                await self._stop.wait()   # stay connected until shutdown
        except Exception as exc:
            self._error = exc
        finally:
            self._ready.set()

    async def _ensure_started(self):
        """Start the connections if needed. The caller must hold the lock."""
        if self._tools is not None:
            return
        if self._task is None:
            self._ready, self._stop = asyncio.Event(), asyncio.Event()
            self._error = None
            self._task = asyncio.create_task(self._run())
        await self._ready.wait()
        if self._tools is None:
            err, self._task, self._error = self._error, None, None
            raise RuntimeError(f"Could not start the MCP servers: {err!r}") from err

    async def _shutdown(self):
        if self._task is None:
            return
        self._stop.set()
        await self._task
        self._task, self._tools = None, None

    async def get_tools(self):
        if self._tools is not None:
            return self._tools
        async with self._lock():
            await self._ensure_started()
        return self._tools

    async def get_tool(self, name: str):
        tools = await self.get_tools()
        for mcp_tool in tools:
            if mcp_tool.name == name:
                return mcp_tool
        available = ", ".join(t.name for t in tools)
        raise RuntimeError(f"MCP tool '{name}' was not found. Available: {available}")

    @asynccontextmanager
    async def session(self):
        """Keep the connections open for one request; the last one out closes them."""
        async with self._lock():
            await self._ensure_started()
            self._users += 1
        try:
            yield self
        finally:
            async with self._lock():
                self._users -= 1
                if self._users == 0:
                    await self._shutdown()

    async def close(self):
        """Disconnect every MCP server. Call from the same event loop that opened them."""
        await self._shutdown()


toolbox = MCPToolbox(build_mcp_config)


async def close_mcp():
    """Run once at the very end of a session."""
    await toolbox.close()


# ---------------------------------------------------------------- Research tools (Tavily, Ignav)
@tool
async def tavily_mcp_search_tool(query: str):
    """
    Search the web for destination and travel research.

    Use ONLY for:
    - hotels
    - neighborhoods
    - attractions
    - food
    - events
    - visa requirements
    - local transport
    - travel tips

    NEVER use this tool for:
    - flights
    - flight prices
    - airlines
    - flight schedules
    - flight booking links

    For any flight-related request, use flights_mcp_search_tool instead.
    """

    mcp_tool = await toolbox.get_tool(TOOL_TAVILY_SEARCH)
    return await mcp_tool.ainvoke({"query": query})


@tool
async def airports_mcp_search_tool(
    query: str,
    limit: int = 5,
):
    """
    Look up airports and their IATA codes.

    Use this before searching flights whenever the correct airport
    code is unknown or when a city has multiple airports.

    Args:
        query:
            City, airport name, metro area, or IATA code.

            Examples:
            "Cologne"
            "Lisbon"
            "London"
            "LHR"

        limit:
            Maximum number of airport matches to return.

    Returns airport information including IATA codes.
    """

    mcp_tool = await toolbox.get_tool(TOOL_AIRPORTS)
    return await mcp_tool.ainvoke({"query": query, "limit": limit})


@tool
async def flights_mcp_search_tool(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
):
    """
    Search live flights and flight prices.

    This is the ONLY tool that may be used for:
    - flight options
    - flight prices
    - airlines
    - flight schedules
    - flight booking links

    Do not use Tavily for flight information.

    Search for one-way or round-trip flights.

    Use IATA airport codes such as CGN, LIS, LHR, JFK.

    If return_date is provided, search for a round trip.
    If return_date is None, search for a one-way flight.

    Dates must use YYYY-MM-DD format.
    """

    mcp_tool = await toolbox.get_tool(TOOL_FLIGHTS)

    payload = {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
    }
    if return_date is not None:
        payload["return_date"] = return_date

    return await mcp_tool.ainvoke(payload)


# ---------------------------------------------------------------- Write tool (our own MCP server)
@tool
async def filesystem_write_mcp_tool(
    filename: str,
    content: str,
):
    """
    Write text content to a .txt file inside the allowed sandbox directory.

    Use this tool to save generated text such as travel plans.

    Args:
        filename:
            Name of the file inside the sandbox, named after the trip
            destination and ending in .txt.

        content:
            The full text content that should be written to the file.

    Important:
    - Files are written only inside the sandbox directory.
    - If the file already exists, its contents may be overwritten.
    """

    mcp_tool = await toolbox.get_tool(TOOL_FS_WRITE)

    # the server itself refuses paths outside the sandbox and non-.txt files
    return await mcp_tool.ainvoke({"filename": filename, "content": content})


if __name__ == "__main__":
    file_mcp.run()  # stdio transport; started by config.build_mcp_config()

