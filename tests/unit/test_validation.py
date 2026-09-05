from unittest.mock import MagicMock, patch
from agents.validation_agent import allowed_statements, validation_agent
from graph.state import DatavoxState


def test_allowed_select_statement():
    result = allowed_statements("select revenue from stores")
    assert result is True


def test_forbidden_drop_statement():
    result = allowed_statements("Drop table revenue")
    assert result is False


def test_forbidden_delete_statement():
    result = allowed_statements("DELETE FROM customers WHERE id = 1")
    assert result is False


def test_forbidden_truncate_statement():
    result = allowed_statements("TRUNCATE TABLE orders")
    assert result is False


def test_validation_agent_blocks_forbidden_sql():
    state: DatavoxState = {
        "session_id": "test-123",
        "user_query": "Delete all users",
        "generated_sql": "DROP TABLE users;",
        "schema_context": "",
        "node_trace": [],
        "current_node": "sql_agent",
        "cached_found": False,
        "retry_count": 3,
        "conversation_history": [],
        "intent_router_error": None,
        "intent_confidence_score": 1.0,
        "is_user_query_ambigous": False,
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

    result_state = validation_agent(state)
    assert result_state["is_sql_valid"] is False
    assert "Forbidden SQL statement" in result_state["validation_error"]
    assert "validation_agent" in result_state["node_trace"]


@patch("agents.validation_agent.get_llm")
def test_validation_agent_approves_valid_sql(mock_get_llm):
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"semantically_aligned": true, "taking_schema_context": true}'
    mock_llm_instance.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm_instance

    state: DatavoxState = {
        "session_id": "test-123",
        "user_query": "What is the total revenue?",
        "generated_sql": "SELECT SUM(total_revenue) FROM regional_sales;",
        "schema_context": "regional_sales table",
        "node_trace": [],
        "current_node": "sql_agent",
        "cached_found": False,
        "retry_count": 3,
        "conversation_history": [],
        "intent_router_error": None,
        "intent_confidence_score": 1.0,
        "is_user_query_ambigous": False,
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

    result_state = validation_agent(state)
    assert result_state["is_sql_valid"] is True
    assert result_state["validation_error"] is None

