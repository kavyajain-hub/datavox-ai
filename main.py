import uuid
import json
import logging
from typing import Optional, List, Dict
from collections import OrderedDict
from graph.builder import graph, checkpointer
from graph.state import DatavoxState
from semantic_cache import get as cache_get, set as cache_set
from db.redis_client import get_redis_client, get_schema_cache
from api.input_validator import validate_input

from config.llm import set_request_llm_credentials
from config.settings import get_settings

logger = logging.getLogger(__name__)

# Redis client and schema cache initialized safely
redis_client = get_redis_client()
schema_cache = get_schema_cache(redis_client)

# Compile LangGraph app once
app = graph.compile(checkpointer=checkpointer)


class BoundedHistory(OrderedDict):
    """LRU-evicting dict for in-memory session history (max 500 sessions)."""
    def __init__(self, max_size=500):
        super().__init__()
        self.max_size = max_size

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.max_size:
            self.popitem(last=False)


# Local in-memory session history fallback when Redis is unavailable
_memory_history: BoundedHistory = BoundedHistory(max_size=500)


def get_history(session_id: str) -> List[dict]:
    """Retrieve session conversation history from Redis or in-memory fallback."""
    if redis_client:
        try:
            data = redis_client.get(f"history:{session_id}")
            return json.loads(data) if data else []
        except Exception as e:
            logger.warning(f"Error fetching history from Redis: {e}")
    return _memory_history.get(session_id, [])


def save_history(session_id: str, history: List[dict]) -> None:
    """Persist session conversation history to Redis or in-memory fallback."""
    _memory_history[session_id] = history
    if redis_client:
        try:
            redis_client.set(f"history:{session_id}", json.dumps(history))
        except Exception as e:
            logger.warning(f"Error saving history to Redis: {e}")


def handle_query_detailed(
    user_query: str,
    session_id: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> dict:
    """Main pipeline detailed entry point: returns complete state, trace, SQL, and response bundle."""
    if not session_id:
        session_id = str(uuid.uuid4())

    # Set request-scoped LLM credentials if provided
    set_request_llm_credentials(api_key=api_key, provider=provider, model=model)

    # Guard against missing API credentials
    settings = get_settings()
    effective_key = api_key or settings.active_api_key
    if not effective_key or effective_key.startswith("your-") or effective_key == "sk-mock-key-for-init":
        return {
            "session_id": session_id,
            "user_query": user_query,
            "final_response": "⚠️ **No API Key detected.** Please click the **Settings (⚙️)** button in the top right to enter your **Google Gemini** or **OpenAI** API key.",
            "generated_sql": None,
            "executed_sql_output": None,
            "node_trace": ["auth_guard"],
            "is_safe": True,
            "is_sql_valid": False,
            "validation_error": "API Key Required",
            "sql_execution_error": None,
            "cached": False
        }

    # Load previous conversation history
    history = get_history(session_id)

    # Input guardrail validation
    is_safe, result = validate_input(user_query)
    if not is_safe:
        return {
            "session_id": session_id,
            "user_query": user_query,
            "final_response": result,
            "generated_sql": None,
            "executed_sql_output": None,
            "node_trace": ["input_validator"],
            "is_safe": False,
            "is_sql_valid": False,
            "validation_error": result,
            "sql_execution_error": None,
            "cached": False
        }

    user_query = result

    # Check semantic cache
    cached_response = cache_get(user_query, redis_client)
    if cached_response is not None:
        exchange = {"role": "user", "content": user_query}
        response = {"role": "assistant", "content": cached_response}
        save_history(session_id, history + [exchange, response])
        return {
            "session_id": session_id,
            "user_query": user_query,
            "final_response": cached_response,
            "generated_sql": None,
            "executed_sql_output": None,
            "node_trace": ["semantic_cache"],
            "is_safe": True,
            "is_sql_valid": True,
            "validation_error": None,
            "sql_execution_error": None,
            "cached": True
        }

    # Initialize graph state
    initial_state: DatavoxState = {
        "session_id": session_id,
        "user_query": user_query,
        "node_trace": [],
        "current_node": "start",
        "cached_found": False,
        "retry_count": 3,
        "schema_context": "",
        "conversation_history": history,

        # Optional fields start as None
        "intent_router_error": None,
        "intent_confidence_score": None,
        "is_user_query_ambigous": None,
        "generated_sql": None,
        "sql_agent_error": None,
        "is_sql_valid": None,
        "validation_error": None,
        "executed_sql_output": None,
        "sql_execution_error": None,
        "result_validator": None,
        "result_validator_error": None,
        "final_response_error": None,
        "final_response": None
    }

    config = {"configurable": {"thread_id": session_id}}

    # Invoke the LangGraph pipeline
    final_state = app.invoke(initial_state, config=config)
    final_response = final_state.get("final_response") or "I could not produce a response for your query."

    # Save to conversation history
    exchange = {"role": "user", "content": user_query}
    response = {"role": "assistant", "content": final_response}
    save_history(session_id, history + [exchange, response])

    # Cache only successful responses from response_agent (never cache clarifications, escalations, or errors)
    if (
        final_state.get("current_node") == "response_agent"
        and not final_state.get("validation_error")
        and not final_state.get("sql_execution_error")
        and not final_state.get("intent_router_error")
    ):
        cache_set(user_query, final_response, redis_client)

    return {
        "session_id": session_id,
        "user_query": user_query,
        "final_response": final_response,
        "generated_sql": final_state.get("generated_sql"),
        "executed_sql_output": final_state.get("executed_sql_output"),
        "node_trace": final_state.get("node_trace", []),
        "is_safe": True,
        "is_sql_valid": final_state.get("is_sql_valid"),
        "validation_error": final_state.get("validation_error"),
        "sql_execution_error": final_state.get("sql_execution_error"),
        "cached": False
    }


def handle_query(user_query: str, session_id: Optional[str] = None) -> str:
    """Convenience entry point returning just the final response string."""
    result = handle_query_detailed(user_query, session_id=session_id)
    return result["final_response"]


if __name__ == "__main__":
    print("Datavox Assistant initialized.")
    test_query = "Show total sales by region"
    print(f"Testing query: '{test_query}'")
    answer = handle_query(test_query)
    print("Response:", answer)