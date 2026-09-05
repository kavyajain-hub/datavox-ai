import pytest
from sqlalchemy import text
from db.connection import get_engine
from agents.execute import execute_agent
from graph.state import DatavoxState


def test_sqlite_connection_and_data():
    engine = get_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM customers;"))
        count = res.scalar()
        assert count == 10

        res_products = conn.execute(text("SELECT COUNT(*) FROM products;"))
        assert res_products.scalar() == 10

        res_orders = conn.execute(text("SELECT COUNT(*) FROM orders;"))
        assert res_orders.scalar() == 10

        res_sales = conn.execute(text("SELECT COUNT(*) FROM regional_sales;"))
        assert res_sales.scalar() == 10


def test_execute_agent_with_real_sqlite_query():
    state: DatavoxState = {
        "session_id": "test-sqlite-1",
        "user_query": "What is the total revenue in the North region?",
        "generated_sql": "SELECT region, SUM(total_revenue) AS total_rev FROM regional_sales WHERE region = 'North' GROUP BY region;",
        "node_trace": [],
        "current_node": "validation_agent",
        "cached_found": False,
        "retry_count": 3,
        "schema_context": "",
        "conversation_history": [],
        "intent_router_error": None,
        "intent_confidence_score": None,
        "is_user_query_ambigous": None,
        "sql_agent_error": None,
        "is_sql_valid": True,
        "validation_error": None,
        "executed_sql_output": None,
        "sql_execution_error": None,
        "result_validator": None,
        "result_validator_error": None,
        "final_response_error": None,
        "final_response": None
    }

    result = execute_agent(state)
    assert result["sql_execution_error"] is None
    assert result["executed_sql_output"] is not None
    assert len(result["executed_sql_output"]) == 1
    assert result["executed_sql_output"][0]["region"] == "North"
    assert result["executed_sql_output"][0]["total_rev"] == 94100.0
    assert "execute_agent" in result["node_trace"]


def test_execute_agent_handles_sqlite_syntax_error():
    state: DatavoxState = {
        "session_id": "test-sqlite-err",
        "user_query": "Invalid query",
        "generated_sql": "SELECT non_existent_column FROM invalid_table;",
        "node_trace": [],
        "current_node": "validation_agent",
        "cached_found": False,
        "retry_count": 3,
        "schema_context": "",
        "conversation_history": [],
        "intent_router_error": None,
        "intent_confidence_score": None,
        "is_user_query_ambigous": None,
        "sql_agent_error": None,
        "is_sql_valid": True,
        "validation_error": None,
        "executed_sql_output": None,
        "sql_execution_error": None,
        "result_validator": None,
        "result_validator_error": None,
        "final_response_error": None,
        "final_response": None
    }

    result = execute_agent(state)
    assert result["sql_execution_error"] is not None
    assert result["executed_sql_output"] is None
    assert "no such table" in result["sql_execution_error"].lower()
    assert "execute_agent" in result["node_trace"]
