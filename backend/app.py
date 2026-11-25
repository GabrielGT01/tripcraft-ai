"""TripCraft FastAPI API.

The frontend is a separate statically exported Next.js application.
FastAPI exposes only the API endpoints.

MCP connections are NOT managed here.

The LangGraph nodes that actually need MCP manage their own
MCP sessions inside pipeline.py.
"""

import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import (
    FastAPI,
    HTTPException,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from langgraph.types import Command

from pydantic import (
    BaseModel,
    Field,
)

from .config import (
    MODEL_NAME,
    SANDBOX_DIR,
    require_env,
)

from .memory import (
    build_checkpointer,
)

from .pipeline import (
    build_graph,
)

from .schemas import (
    get_interrupt,
)

from .tools import (
    close_mcp,
)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

require_env()


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def get_cors_origins() -> list[str]:
    """
    Read allowed frontend origins from the environment.

    Example:

        CORS_ORIGINS=http://localhost:3000

    Multiple origins may be comma-separated.
    """

    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000",
    )

    return [
        origin.strip()
        for origin in raw.split(",")
        if origin.strip()
    ]


# ---------------------------------------------------------------------------
# FastAPI lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    """
    FastAPI application lifecycle.

    MCP connections are normally opened and closed
    inside the graph nodes that need them.

    close_mcp() here is just final cleanup when the
    application itself shuts down.
    """

    yield

    await close_mcp()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TripCraft AI API",
    description=(
        "FastAPI + LangGraph + MCP "
        "travel-planning backend."
    ),
    version="4.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Memory
#
# build_checkpointer() creates the DynamoDBSaver.
# ---------------------------------------------------------------------------

checkpointer = build_checkpointer()


# ---------------------------------------------------------------------------
# LangGraph
#
# pipeline.py builds the graph.
#
# The graph receives our DynamoDB checkpointer.
# ---------------------------------------------------------------------------

graph = build_graph(
    checkpointer=checkpointer
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class TripRequest(BaseModel):
    """
    Start a new trip-planning workflow.
    """

    question: str = Field(
        min_length=3,
    )

    thread_id: str = Field(
        min_length=8,
        max_length=128,
    )


class ResumeRequest(BaseModel):
    """
    Resume a LangGraph workflow after an interrupt.
    """

    thread_id: str = Field(
        min_length=8,
        max_length=128,
    )

    action: Literal[
        "approve",
        "revise",
        "inquire",
    ] | None = None

    message: str | None = None


# ---------------------------------------------------------------------------
# LangGraph configuration
# ---------------------------------------------------------------------------

def graph_config(
    thread_id: str,
) -> dict:
    """
    LangGraph uses thread_id to identify one conversation.
    """

    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


# ---------------------------------------------------------------------------
# Read a saved text file
# ---------------------------------------------------------------------------

def read_saved_file(
    filename: str | None,
) -> str | None:
    """
    Read the travel-plan text file from the configured sandbox.
    """

    if not filename:
        return None

    try:
        return (
            SANDBOX_DIR
            / filename
        ).read_text(
            encoding="utf-8"
        )

    except OSError:
        return None


# ---------------------------------------------------------------------------
# Convert LangGraph result into frontend JSON
# ---------------------------------------------------------------------------

def format_result(
    thread_id: str,
    result: dict,
) -> dict:
    """
    Convert LangGraph state into a clean API response.
    """

    pending = get_interrupt(
        result
    )

    details = result.get(
        "travel_framed_details"
    )


    if details is not None:
        details = (
            details.model_dump()
        )


    # -----------------------------------------------------------------------
    # Graph paused because it needs something from the user.
    # -----------------------------------------------------------------------

    if pending:

        interrupt_type = (
            "clarify"
            if "missing" in pending
            else "decision"
        )

        return {
            "thread_id": (
                thread_id
            ),

            "status": (
                "waiting_for_user"
            ),

            "interrupt_type": (
                interrupt_type
            ),

            "interrupt": (
                pending
            ),

            "travel_details": (
                details
            ),

            "plan": result.get(
                "travel_search_result"
            ),
        }


    # -----------------------------------------------------------------------
    # Graph finished.
    # -----------------------------------------------------------------------

    saved_filename = (
        result.get(
            "saved_filename"
        )
    )


    return {
        "thread_id": (
            thread_id
        ),

        "status": (
            "finished"
        ),

        "travel_details": (
            details
        ),

        "plan": result.get(
            "travel_search_result"
        ),

        "saved_filename": (
            saved_filename
        ),

        "saved_file": result.get(
            "saved_file"
        ),

        "saved_file_content": (
            read_saved_file(
                saved_filename
            )
        ),
    }


# ---------------------------------------------------------------------------
# Run LangGraph
#
# IMPORTANT:
#
# We do NOT open MCP here anymore.
#
# app.py simply runs the graph.
#
# pipeline.py decides which nodes need MCP.
# ---------------------------------------------------------------------------

async def run_graph(
    graph_input,
    thread_id: str,
) -> dict:

    try:

        result = await graph.ainvoke(
            graph_input,
            config=graph_config(
                thread_id
            ),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        ) from exc


    return format_result(
        thread_id,
        result,
    )


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():

    return {
        "name": (
            "TripCraft AI API"
        ),
        "status": "ok",
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "model": MODEL_NAME,
        "authentication": (
            "disabled"
        ),
        "frontend": (
            "separate-static-nextjs"
        ),
        "memory": (
            "DynamoDBSaver"
        ),
    }


# ---------------------------------------------------------------------------
# Start trip
# ---------------------------------------------------------------------------

@app.post("/api/trip/start")
async def start_trip(
    request: TripRequest,
):

    thread_id = (
        request.thread_id.strip()
    )

    config = graph_config(
        thread_id
    )


    # -----------------------------------------------------------------------
    # Check whether this conversation is already waiting at an interrupt.
    # -----------------------------------------------------------------------

    snapshot = (
        await graph.aget_state(
            config
        )
    )


    if snapshot.next:

        raise HTTPException(
            status_code=409,
            detail=(
                "This conversation is waiting "
                "for your answer. "
                "Continue it first."
            ),
        )


    # -----------------------------------------------------------------------
    # Starting LangGraph state
    # -----------------------------------------------------------------------

    graph_input = {
        "question": (
            request.question.strip()
        ),

        "reframed_question": (
            None
        ),

        "travel_framed_details": (
            None
        ),

        "missing_info": [],

        "travel_search_result": "",

        "saved_file": "",

        "saved_filename": "",
    }


    return await run_graph(
        graph_input,
        thread_id,
    )


# ---------------------------------------------------------------------------
# Resume trip
# ---------------------------------------------------------------------------

@app.post("/api/trip/resume")
async def resume_trip(
    request: ResumeRequest,
):

    thread_id = (
        request.thread_id.strip()
    )

    config = graph_config(
        thread_id
    )


    # -----------------------------------------------------------------------
    # Retrieve current LangGraph state from the checkpointer.
    # -----------------------------------------------------------------------

    snapshot = (
        await graph.aget_state(
            config
        )
    )


    # -----------------------------------------------------------------------
    # No workflow exists for this thread.
    # -----------------------------------------------------------------------

    if not snapshot.values:

        raise HTTPException(
            status_code=404,
            detail=(
                "No active trip was found "
                "for this browser conversation."
            ),
        )


    # -----------------------------------------------------------------------
    # Workflow has already finished.
    # -----------------------------------------------------------------------

    if not snapshot.next:

        raise HTTPException(
            status_code=409,
            detail=(
                "This workflow is already "
                "finished. Start a new request."
            ),
        )


    # -----------------------------------------------------------------------
    # Clarification reply
    #
    # Example:
    #
    # {
    #     "message": "Cologne to Lisbon..."
    # }
    # -----------------------------------------------------------------------

    if request.action is None:

        message = (
            request.message
            or ""
        ).strip()


        if not message:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Please provide "
                    "an answer."
                ),
            )


        resume_value = {
            "message": message,
        }


    # -----------------------------------------------------------------------
    # Human decision
    #
    # approve
    # revise
    # inquire
    # -----------------------------------------------------------------------

    else:

        resume_value = {
            "action": (
                request.action
            ),
        }


        message = (
            request.message
            or ""
        ).strip()


        if message:

            resume_value[
                "message"
            ] = message


    # -----------------------------------------------------------------------
    # Continue the paused LangGraph workflow.
    # -----------------------------------------------------------------------

    return await run_graph(
        Command(
            resume=resume_value
        ),
        thread_id,
    )