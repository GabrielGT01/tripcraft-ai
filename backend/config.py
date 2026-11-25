"""Environment, paths, AWS settings, and MCP server configuration."""

import logging
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# LOAD LOCAL .env
#
# Lambda already provides its environment variables.
# Locally, this loads values from your .env file.
# ============================================================

load_dotenv()


# ============================================================
# DISABLE TRACING
# ============================================================

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"


# ============================================================
# LOGGING
# ============================================================

logging.getLogger(
    "fastmcp"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "fastmcp.server.providers.proxy"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "httpx"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "httpcore"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "httpx2"
).setLevel(
    logging.WARNING
)

logging.getLogger(
    "openai"
).setLevel(
    logging.WARNING
)


# ============================================================
# WARNINGS
# ============================================================

warnings.filterwarnings(
    "ignore",
    message=r".*langchain\.mcp.*beta.*",
)


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = os.getenv(
    "TRIP_PLANNER_MODEL",
    "gpt-4o",
)


# ============================================================
# AWS / MEMORY CONFIGURATION
#
# memory.py imports these values.
# ============================================================

AWS_REGION = os.getenv(
    "AWS_REGION",
    os.getenv(
        "AWS_DEFAULT_REGION",
        "us-east-1",
    ),
)


CHECKPOINT_TABLE = os.getenv(
    "CHECKPOINT_TABLE",
    "tripcraft-checkpoints",
)


CHECKPOINT_BUCKET = os.getenv(
    "CHECKPOINT_BUCKET",
)


# ============================================================
# REQUIRED MEMORY ENVIRONMENT VARIABLES
#
# CHECKPOINT_TABLE already has a default.
# AWS_REGION also has a default.
#
# CHECKPOINT_BUCKET has no safe default because it must be
# your actual S3 checkpoint bucket.
# ============================================================

MEMORY_REQUIRED_ENV = (
    "CHECKPOINT_BUCKET",
)


# ============================================================
# SANDBOX
#
# Lambda:
#
# TRIP_PLANNER_SANDBOX=/tmp/travel_plan_file
#
# Local fallback:
#
# travel_plan_file/
# ============================================================

SANDBOX_DIR = Path(
    os.getenv(
        "TRIP_PLANNER_SANDBOX",
        "travel_plan_file",
    )
).resolve()


# ============================================================
# REQUIRED API KEYS
# ============================================================

REQUIRED_ENV = (
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "IGNAV_API_KEY",
)


# ============================================================
# MCP TOOL NAMES
# ============================================================

TOOL_TAVILY_SEARCH = (
    "tavily_tavily_search"
)

TOOL_AIRPORTS = (
    "ignav_search_airports"
)

TOOL_FLIGHTS = (
    "ignav_search_flights"
)

TOOL_FS_WRITE = (
    "tripfiles_write_file"
)


# ============================================================
# ENVIRONMENT VALIDATION
#
# IMPORTANT:
#
# This function can now be used in TWO ways:
#
# require_env()
#     -> checks normal API keys
#
# require_env(MEMORY_REQUIRED_ENV)
#     -> checks memory/S3 configuration
#
# This matches memory.py.
# ============================================================

def require_env(
    required_names=REQUIRED_ENV,
) -> None:
    """
    Check that the requested environment variables exist.
    """

    missing = [
        name
        for name in required_names
        if not os.getenv(name)
    ]


    if missing:

        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# MCP CONFIGURATION
# ============================================================

def build_mcp_config() -> dict:
    """
    Build the MCP server configuration.

    Remote MCP servers:
    - Tavily
    - Ignav

    Local MCP server:
    - tripfiles


    tripfiles is launched as:

        python -m backend.tools <sandbox>

    rather than:

        python backend/tools.py


    Using -m keeps backend.tools inside the backend package
    so relative imports work correctly in Lambda.
    """

    # Checks:
    #
    # OPENAI_API_KEY
    # TAVILY_API_KEY
    # IGNAV_API_KEY
    #
    # because REQUIRED_ENV is the default argument.
    require_env()


    return {
        "mcpServers": {

            # ------------------------------------------------
            # TAVILY
            # ------------------------------------------------

            "tavily": {
                "url": (
                    "https://mcp.tavily.com/mcp/"
                    f"?tavilyApiKey="
                    f"{os.environ['TAVILY_API_KEY']}"
                )
            },


            # ------------------------------------------------
            # IGNAV
            # ------------------------------------------------

            "ignav": {
                "url": (
                    "https://ignav.com/mcp"
                ),

                "headers": {
                    "Authorization": (
                        "Bearer "
                        f"{os.environ['IGNAV_API_KEY']}"
                    )
                },
            },


            # ------------------------------------------------
            # TRIPFILES
            #
            # Starts our own Python MCP filesystem server.
            # ------------------------------------------------

            "tripfiles": {
                "command": sys.executable,

                "args": [
                    "-m",
                    "backend.tools",
                    str(SANDBOX_DIR),
                ],
            },
        }
    }