from unittest.mock import MagicMock, patch
from agents.terminal_node import clarify_agent, escalate_agent
from agents.intent_router import intent_router
from agents.sql_agent import sql_agent
from agents.execute import execute_agent
from agents.result_validator import result_validator_agent
from agents.response import response_agent
from graph.state import DatavoxState


def create_mock_state() -> DatavoxState:
    return {
        "session_id": "test-session-1",
        "user_query": "Show revenue for 2024",
        "node_trace": [],
        "current_node": "start",
        "cached_found": False,
        "retry_count": 3,
        "schema_context": "regional_sales table",
        "conversation_history": [],
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


def test_clarify_agent():
    state = create_mock_state()
    res = clarify_agent(state)
    assert res["current_node"] == "clarify_agent"
    assert "clarify" in res["final_response"].lower()
    assert "clarify_agent" in res["node_trace"]


def test_escalate_agent():
    state = create_mock_state()
    state["validation_error"] = "Fatal error"
    res = escalate_agent(state)
    assert res["current_node"] == "escalate_agent"
    assert "notified" in res["final_response"].lower()
    assert "escalate_agent" in res["node_trace"]


@patch("agents.intent_router.get_llm")
def test_intent_router_sql_agent(mock_get_llm):
    mock_llm = MagicMock()
    mock_res = MagicMock()
    mock_res.content = '{"intent": "sql_agent", "confidence_score": 0.98}'
    mock_llm.invoke.return_value = mock_res
    mock_get_llm.return_value = mock_llm

    state = create_mock_state()
    res = intent_router(state)
    assert res["is_user_query_ambigous"] is False
    assert res["intent_confidence_score"] == 0.98
    assert "intent_router" in res["node_trace"]


@patch("agents.sql_agent.get_llm")
def test_sql_agent_generates_sql(mock_get_llm):
    mock_llm = MagicMock()
    mock_res = MagicMock()
    mock_res.content = '{"sql": "SELECT SUM(total_revenue) FROM regional_sales WHERE sales_date >= \'2024-01-01\'"}'
    mock_llm.invoke.return_value = mock_res
    mock_get_llm.return_value = mock_llm

    state = create_mock_state()
    res = sql_agent(state)
    assert res["generated_sql"] == "SELECT SUM(total_revenue) FROM regional_sales WHERE sales_date >= '2024-01-01'"
    assert res["sql_agent_error"] is None
    assert "sql_agent" in res["node_trace"]


@patch("agents.execute.get_engine")
def test_execute_agent_success(mock_get_engine):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    row_mapping = {"total_revenue": 50000}
    mock_row = MagicMock()
    mock_row.mapping = row_mapping
    mock_result.fetchall.return_value = [mock_row]
    mock_result.mappings.return_value.all.return_value = [{"total_revenue": 50000}]

    mock_conn.execute.return_value = mock_result
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_get_engine.return_value = mock_engine

    state = create_mock_state()
    state["generated_sql"] = "SELECT SUM(total_revenue) FROM regional_sales;"
    res = execute_agent(state)

    assert res["executed_sql_output"] == [{"total_revenue": 50000}]
    assert res["sql_execution_error"] is None
    assert "execute_agent" in res["node_trace"]


@patch("agents.result_validator.get_llm")
def test_result_validator_agent(mock_get_llm):
    mock_llm = MagicMock()
    mock_res = MagicMock()
    mock_res.content = '{"is_valid": true, "reason": "Query answered the question accurately"}'
    mock_llm.invoke.return_value = mock_res
    mock_get_llm.return_value = mock_llm

    state = create_mock_state()
    state["executed_sql_output"] = [{"total_revenue": 50000}]
    res = result_validator_agent(state)
    assert res["result_validator"] is True
    assert "result_validator_agent" in res["node_trace"]


@patch("agents.response.get_llm")
def test_response_agent(mock_get_llm):
    mock_llm = MagicMock()
    mock_res = MagicMock()
    mock_res.content = "The total revenue for 2024 was $50,000 across all regions."
    mock_llm.invoke.return_value = mock_res
    mock_get_llm.return_value = mock_llm

    state = create_mock_state()
    state["executed_sql_output"] = [{"total_revenue": 50000}]
    res = response_agent(state)
    assert res["final_response"] == "The total revenue for 2024 was $50,000 across all regions."
    assert "response_agent" in res["node_trace"]

