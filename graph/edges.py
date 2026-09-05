from graph.state import DatavoxState


def route_intent(state: DatavoxState) -> str:
    """Route from intent_router to clarify agent, escalate agent, or sql agent."""
    if state.get('intent_router_error'):
        return "escalate_agent"

    is_ambiguous = state.get('is_user_query_ambigous', False)
    confidence = state.get('intent_confidence_score', 0.0) or 0.0

    if is_ambiguous or confidence < 0.9:
        return "ask_clarificatory_questions"
    return "sql_agent"


def route_validation_agent(state: DatavoxState) -> str:
    """Route from validation_agent to escalate, retry sql_agent, or proceed to execute_agent."""
    val_error = state.get('validation_error') or ""
    val_error_lower = val_error.lower()
    retry_count = state.get('retry_count', 0) or 0

    if val_error and "forbidden" in val_error_lower:
        return "escalate_agent"

    if val_error and ("semantic" in val_error_lower or "schema" in val_error_lower):
        if retry_count > 0:
            return "sql_agent"
        return "escalate_agent"

    if val_error:
        if retry_count > 0:
            return "sql_agent"
        return "escalate_agent"

    return "execute_agent"


def route_after_execution(state: DatavoxState) -> str:
    """Route after execution: retry SQL on failure, escalate if retries exhausted, or generate response."""
    has_error = bool(state.get('sql_execution_error'))
    validator_failed = state.get("result_validator") is False
    retry_count = state.get('retry_count', 0) or 0

    if has_error or validator_failed:
        if retry_count > 0:
            return "sql_agent"
        return "escalate_agent"

    return "response_agent"
