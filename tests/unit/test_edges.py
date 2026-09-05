from graph.edges import route_intent, route_validation_agent, route_after_execution
from graph.state import DatavoxState


def create_base_state() -> DatavoxState:
    return {
        "session_id": "test-session",
        "user_query": "select revenue",
        "node_trace": [],
        "current_node": "start",
        "cached_found": False,
        "retry_count": 3,
        "schema_context": "",
        "conversation_history": [],
        "intent_router_error": None,
        "intent_confidence_score": 0.95,
        "is_user_query_ambigous": False,
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


def test_route_intent_clear():
    state = create_base_state()
    state["is_user_query_ambigous"] = False
    state["intent_confidence_score"] = 0.95
    assert route_intent(state) == "sql_agent"


def test_route_intent_ambiguous():
    state = create_base_state()
    state["is_user_query_ambigous"] = True
    assert route_intent(state) == "ask_clarificatory_questions"


def test_route_intent_low_confidence():
    state = create_base_state()
    state["intent_confidence_score"] = 0.70
    assert route_intent(state) == "ask_clarificatory_questions"


def test_route_validation_agent_valid():
    state = create_base_state()
    state["validation_error"] = None
    assert route_validation_agent(state) == "execute_agent"


def test_route_validation_agent_forbidden():
    state = create_base_state()
    state["validation_error"] = "Forbidden SQL statement"
    assert route_validation_agent(state) == "escalate_agent"


def test_route_validation_agent_retry():
    state = create_base_state()
    state["validation_error"] = "Failed because the query is not taking right schema"
    state["retry_count"] = 2
    assert route_validation_agent(state) == "sql_agent"


def test_route_validation_agent_exhausted_retries():
    state = create_base_state()
    state["validation_error"] = "Failed because the query is not taking right schema"
    state["retry_count"] = 0
    assert route_validation_agent(state) == "escalate_agent"


def test_route_after_execution_success():
    state = create_base_state()
    state["sql_execution_error"] = None
    state["result_validator"] = True
    assert route_after_execution(state) == "response_agent"


def test_route_after_execution_error_retries():
    state = create_base_state()
    state["sql_execution_error"] = "Syntax error in SQL"
    state["retry_count"] = 2
    assert route_after_execution(state) == "sql_agent"


def test_route_after_execution_error_exhausted():
    state = create_base_state()
    state["sql_execution_error"] = "Syntax error in SQL"
    state["retry_count"] = 0
    assert route_after_execution(state) == "escalate_agent"
