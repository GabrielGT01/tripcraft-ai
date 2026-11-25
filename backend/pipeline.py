"""Graph nodes and the LangGraph pipeline.

    START -> intake -> (missing info? -> clarify -> intake)
                    -> planning -> human_decision
                          approve -> writer -> END
                          revise  -> intake
                          inquire -> END
"""

import datetime
import logging
from typing import Literal

from langchain.agents import create_agent
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from langgraph.checkpoint.memory import (
    MemorySaver,
)
from langgraph.checkpoint.serde.jsonplus import (
    JsonPlusSerializer,
)
from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from langgraph.types import (
    Command,
    interrupt,
)

from .config import (
    MODEL_NAME,
    require_env,
)

from .prompts import (
    INTAKE_PROMPT,
    TRAVEL_AGENT_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)

from .schemas import (
    FlightDetails,
    TravelDetails,
    TravelState,
    as_dict,
    get_missing,
    make_filename,
)

from .tools import (
    airports_mcp_search_tool,
    filesystem_write_mcp_tool,
    flights_mcp_search_tool,
    tavily_mcp_search_tool,
    toolbox,
)


logger = logging.getLogger(
    "trip_planner"
)


# ---------------------------------------------------------------------------
# Tool error logging
# ---------------------------------------------------------------------------

def log_tool_errors(
    messages,
) -> None:
    """
    Log tool failures so they are visible
    in CloudWatch.
    """

    for message in messages:
        if (
            isinstance(
                message,
                ToolMessage,
            )
            and message.status == "error"
        ):
            logger.warning(
                "Tool %s failed: %s",
                message.name,
                str(
                    message.content
                )[:500],
            )


def make_intake_node(llm):

    chain = (
        INTAKE_PROMPT
        | llm.with_structured_output(
            TravelDetails
        )
    )

    async def intake(
        state: TravelState,
    ) -> dict:

        query = (
            state.get(
                "reframed_question"
            )
            or state["question"]
        )

        earlier = [
            message.content
            for message in (
                state.get("messages")
                or []
            )
            if isinstance(
                message,
                HumanMessage,
            )
        ]

        conversation = "\n".join(
            [
                *earlier,
                query,
            ]
        )

        try:
            details = (
                await chain.ainvoke(
                    {
                        "today": (
                            datetime.date
                            .today()
                            .isoformat()
                        ),
                        "conversation": (
                            conversation
                        ),
                    }
                )
            )

        except Exception as exc:
            logger.warning(
                "Intake failed: %r",
                exc,
            )

            return {
                "messages": [
                    HumanMessage(
                        content=query
                    )
                ],

                "reframed_question": None,

                "travel_framed_details": (
                    None
                ),

                "missing_info": [
                    (
                        "exact dates "
                        "(day, month and year); "
                        "I could not read them"
                    )
                ],
            }

        return {
            "messages": [
                HumanMessage(
                    content=query
                )
            ],

            "reframed_question": None,

            "travel_framed_details": (
                details
            ),

            "missing_info": (
                get_missing(details)
            ),
        }

    return intake


def clarify_node(
    state: TravelState,
) -> Command[
    Literal["intake"]
]:

    payload = {
        "question": (
            "I need a few more details "
            "before I can search:"
        ),

        "missing": (
            state["missing_info"]
        ),
    }

    while True:

        reply = as_dict(
            interrupt(payload)
        )

        message = (
            reply.get("message")
            or ""
        ).strip()

        if message:
            return Command(
                update={
                    "reframed_question": (
                        message
                    )
                },
                goto="intake",
            )

        payload = {
            **payload,
            "error": (
                "Please type your answer."
            ),
        }


# ---------------------------------------------------------------------------
# Planning node
#
# THIS is where MCP is actually required.
#
# We open MCP only when we reach this node.
# ---------------------------------------------------------------------------

def make_planning_node(llm):

    agent = create_agent(
        model=llm,

        tools=[
            airports_mcp_search_tool,
            flights_mcp_search_tool,
            tavily_mcp_search_tool,
        ],

        system_prompt=(
            TRAVEL_AGENT_SYSTEM_PROMPT
        ),
    )

    async def planning(
        state: TravelState,
    ) -> dict:

        travel_details_json = (
            state[
                "travel_framed_details"
            ].model_dump_json(
                indent=2
            )
        )

        # ------------------------------------------------------------
        # MCP starts HERE.
        #
        # Not during intake.
        # Not during clarification.
        # ------------------------------------------------------------

        async with toolbox.session():

            response = (
                await agent.ainvoke(
                    {
                        "messages": [
                            {
                                "role": (
                                    "user"
                                ),

                                "content": (
                                    "Research and plan "
                                    "the complete trip "
                                    "using the structured "
                                    "travel details below."
                                    "\n\n"
                                    "Follow the required "
                                    "tool-routing rules "
                                    "exactly."
                                    "\n\n"
                                    "Travel details:\n"
                                    f"{travel_details_json}"
                                ),
                            }
                        ]
                    }
                )
            )

        log_tool_errors(
            response["messages"]
        )

        final_answer = (
            response[
                "messages"
            ][-1].content
        )

        return {
            "travel_search_result": (
                final_answer
            ),

            "messages": [
                AIMessage(
                    content=final_answer
                )
            ],
        }

    return planning


# ---------------------------------------------------------------------------
# Human decision node
#
# No MCP needed.
# ---------------------------------------------------------------------------

def human_decision_node(
    state: TravelState,
) -> Command[
    Literal[
        "writer",
        "intake",
        "__end__",
    ]
]:

    payload = {
        "presentation": (
            state[
                "travel_search_result"
            ]
        ),

        "question": (
            "What would you like "
            "to do?"
        ),

        "options": {
            "inquire": (
                "Keep these options "
                "and end search"
            ),

            "revise": (
                "Change the trip/search "
                "and search something new"
            ),

            "approve": (
                "Approve these options, "
                "go ahead and create "
                "a txt file"
            ),
        },
    }

    while True:

        response = as_dict(
            interrupt(payload)
        )

        action = response.get(
            "action"
        )

        if action == "approve":
            return Command(
                goto="writer"
            )

        if action == "inquire":
            return Command(
                goto=END
            )

        if action == "revise":

            message = (
                response.get(
                    "message"
                )
                or ""
            ).strip()

            if message:
                return Command(
                    update={
                        "reframed_question": (
                            message
                        )
                    },
                    goto="intake",
                )

            error = (
                "'revise' needs a "
                "'message' describing "
                "the change."
            )

        else:
            error = (
                f"Unknown action "
                f"{action!r}. "
                "Use 'approve', "
                "'revise' or "
                "'inquire'."
            )

        payload = {
            **payload,
            "error": error,
        }


# ---------------------------------------------------------------------------
# Writer node
#
# This DOES need MCP because it calls tripfiles.
# ---------------------------------------------------------------------------

def make_writer_node(llm):

    agent = create_agent(
        model=llm,

        tools=[
            filesystem_write_mcp_tool
        ],

        system_prompt=(
            WRITER_SYSTEM_PROMPT
        ),
    )

    async def writer(
        state: TravelState,
    ) -> dict:

        final_trip_plan = (
            state.get(
                "travel_search_result"
            )
        )

        filename = make_filename(
            state[
                "travel_framed_details"
            ].flight.destination
        )

        # ------------------------------------------------------------
        # Start MCP only because writer needs tripfiles.
        # ------------------------------------------------------------

        async with toolbox.session():

            response = (
                await agent.ainvoke(
                    {
                        "messages": [
                            {
                                "role": (
                                    "user"
                                ),

                                "content": (
                                    "Save the following "
                                    "completed travel plan "
                                    "using exactly this "
                                    "filename: "
                                    f"{filename}"
                                    "\n\n"
                                    "Do not change any "
                                    "factual information."
                                    "\n\n"
                                    f"{final_trip_plan}"
                                ),
                            }
                        ]
                    }
                )
            )

        log_tool_errors(
            response["messages"]
        )

        wrote = any(
            isinstance(
                message,
                ToolMessage,
            )
            and (
                message.status
                != "error"
            )
            for message
            in response["messages"]
        )

        return {
            "saved_file": (
                response[
                    "messages"
                ][-1].content
            ),

            "saved_filename": (
                filename
                if wrote
                else ""
            ),
        }

    return writer


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_intake(
    state: TravelState,
) -> Literal[
    "clarify",
    "planning",
]:

    if state["missing_info"]:
        return "clarify"

    return "planning"


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

def build_serde() -> (
    JsonPlusSerializer
):

    return JsonPlusSerializer(
        allowed_msgpack_modules=[
            (
                TravelDetails.__module__,
                TravelDetails.__name__,
            ),
            (
                FlightDetails.__module__,
                FlightDetails.__name__,
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph(
    llm=None,
    checkpointer=None,
):

    require_env()

    llm = (
        llm
        or ChatOpenAI(
            model=MODEL_NAME,
            temperature=0,
        )
    )

    workflow = StateGraph(
        TravelState
    )

    workflow.add_node(
        "intake",
        make_intake_node(llm),
    )

    workflow.add_node(
        "clarify",
        clarify_node,
    )

    workflow.add_node(
        "planning",
        make_planning_node(llm),
    )

    workflow.add_node(
        "human_decision",
        human_decision_node,
    )

    workflow.add_node(
        "writer",
        make_writer_node(llm),
    )


    workflow.add_edge(
        START,
        "intake",
    )


    workflow.add_conditional_edges(
        "intake",

        route_after_intake,

        {
            "clarify": "clarify",
            "planning": "planning",
        },
    )


    workflow.add_edge(
        "planning",
        "human_decision",
    )


    workflow.add_edge(
        "writer",
        END,
    )


    # If your AWS app injects DynamoDBSaver,
    # this keeps using it.
    #
    # The MemorySaver fallback is only useful
    # for local/notebook testing.

    if checkpointer is None:
        checkpointer = MemorySaver(
            serde=build_serde()
        )


    return workflow.compile(
        checkpointer=checkpointer
    )