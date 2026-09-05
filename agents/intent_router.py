import json
from graph.state import DatavoxState
from config.llm import get_llm


def intent_router(state: DatavoxState) -> DatavoxState:
    """Classify user query intent into sql_agent or need_clarification with confidence score."""
    user_query = state.get('user_query', '')

    prompt = f"""
        You are an analyzer that identifies the intent of the user's query and classifies it into 2 buckets:
        1. "sql_agent": The user is asking a data/analytical question that can be answered with a database query.
        2. "need_clarification": The query is ambiguous, missing vital parameters, or not understandable.

        User query: {user_query}

        Output strictly in JSON format:
        {{
            "intent": "sql_agent" or "need_clarification",
            "confidence_score": 0.95
        }}
    """
    try:
        llm = get_llm(temperature=0)
        response = llm.invoke(prompt)
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(content)
        intent = parsed.get("intent", "need_clarification")
        confidence_score = float(parsed.get("confidence_score", 0.0))

        is_ambiguous = (intent == "need_clarification")

        return {
            **state,
            "is_user_query_ambigous": is_ambiguous,
            "current_node": "intent_router",
            "node_trace": state.get("node_trace", []) + ['intent_router'],
            "intent_confidence_score": confidence_score,
            "intent_router_error": None
        }

    except Exception as e:
        return {
            **state,
            "is_user_query_ambigous": True,
            "current_node": "intent_router",
            "node_trace": state.get("node_trace", []) + ['intent_router'],
            "intent_confidence_score": 0.0,
            "intent_router_error": str(e)
        }