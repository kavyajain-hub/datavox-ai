import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import DatavoxState
from config.settings import get_settings

from agents.intent_router import intent_router
from agents.sql_agent import sql_agent
from agents.validation_agent import validation_agent
from agents.execute import execute_agent
from agents.response import response_agent
from agents.terminal_node import clarify_agent, escalate_agent
from agents.result_validator import result_validator_agent
from graph.edges import route_intent, route_validation_agent, route_after_execution

logger = logging.getLogger(__name__)
settings = get_settings()


def get_checkpointer():
    """Attempt to initialize PostgresSaver checkpointer, fallback to MemorySaver if unavailable."""
    url = settings.checkpoint_db_url
    # If a real non-default postgres URL is configured, try connecting
    if url and not url.startswith("postgresql://postgres:postgres@localhost"):
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            cm = PostgresSaver.from_conn_string(url)
            if hasattr(cm, "__enter__"):
                saver = cm.__enter__()
                if hasattr(saver, "setup"):
                    saver.setup()
                return saver
            return cm
        except Exception as e:
            logger.warning(f"Could not initialize PostgresSaver ({e}), falling back to MemorySaver.")
    return MemorySaver()


checkpointer = get_checkpointer()

graph = StateGraph(DatavoxState)

# Add nodes
graph.add_node("intent_router", intent_router)
graph.add_node("ask_clarificatory_questions", clarify_agent)
graph.add_node("sql_agent", sql_agent)
graph.add_node("validation_agent", validation_agent)
graph.add_node("execute_agent", execute_agent)
graph.add_node("response_agent", response_agent)
graph.add_node("escalate_agent", escalate_agent)
graph.add_node("result_validator_agent", result_validator_agent)

# Set entry point
graph.set_entry_point("intent_router")

# Add edges
graph.add_conditional_edges(
    "intent_router",
    route_intent,
    {
        "ask_clarificatory_questions": "ask_clarificatory_questions",
        "escalate_agent": "escalate_agent",
        "sql_agent": "sql_agent"
    }
)

graph.add_edge("sql_agent", "validation_agent")

graph.add_conditional_edges(
    "validation_agent",
    route_validation_agent,
    {
        "escalate_agent": "escalate_agent",
        "sql_agent": "sql_agent",
        "execute_agent": "execute_agent"
    }
)

graph.add_edge("execute_agent", "result_validator_agent")

graph.add_conditional_edges(
    "result_validator_agent",
    route_after_execution,
    {
        "sql_agent": "sql_agent",
        "escalate_agent": "escalate_agent",
        "response_agent": "response_agent"
    }
)

graph.add_edge("response_agent", END)
graph.add_edge("ask_clarificatory_questions", END)
graph.add_edge("escalate_agent", END)
