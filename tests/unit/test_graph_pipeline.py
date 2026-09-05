from unittest.mock import MagicMock, patch
from graph.builder import graph, MemorySaver
from graph.state import DatavoxState


def test_graph_compilation():
    memory_checkpointer = MemorySaver()
    compiled_app = graph.compile(checkpointer=memory_checkpointer)
    assert compiled_app is not None


@patch("agents.response.get_llm")
@patch("agents.result_validator.get_llm")
@patch("agents.execute.get_engine")
@patch("agents.validation_agent.get_llm")
@patch("agents.sql_agent.get_llm")
@patch("agents.intent_router.get_llm")
def test_full_pipeline_flow(
    mock_intent_get_llm,
    mock_sql_get_llm,
    mock_val_get_llm,
    mock_engine,
    mock_res_val_get_llm,
    mock_resp_get_llm
):
    # 1. Intent router response
    mock_intent_llm = MagicMock()
    intent_res = MagicMock()
    intent_res.content = '{"intent": "sql_agent", "confidence_score": 0.98}'
    mock_intent_llm.invoke.return_value = intent_res
    mock_intent_get_llm.return_value = mock_intent_llm

    # 2. SQL agent response
    mock_sql_llm = MagicMock()
    sql_res = MagicMock()
    sql_res.content = '{"sql": "SELECT SUM(total_revenue) FROM regional_sales;"}'
    mock_sql_llm.invoke.return_value = sql_res
    mock_sql_get_llm.return_value = mock_sql_llm

    # 3. Validation agent response
    mock_val_llm = MagicMock()
    val_res = MagicMock()
    val_res.content = '{"semantically_aligned": true, "taking_schema_context": true}'
    mock_val_llm.invoke.return_value = val_res
    mock_val_get_llm.return_value = mock_val_llm

    # 4. Execution agent mock engine
    conn_mock = MagicMock()
    result_mock = MagicMock()
    row_mock = MagicMock()
    row_mock.mapping = {"total_revenue": 100000}
    result_mock.fetchall.return_value = [row_mock]
    result_mock.mappings.return_value.all.return_value = [{"total_revenue": 100000}]
    conn_mock.execute.return_value = result_mock
    mock_engine_instance = MagicMock()
    mock_engine_instance.connect.return_value.__enter__.return_value = conn_mock
    mock_engine.return_value = mock_engine_instance

    # 5. Result validator response
    mock_res_val_llm = MagicMock()
    res_val = MagicMock()
    res_val.content = '{"is_valid": true, "reason": "Accurate calculation"}'
    mock_res_val_llm.invoke.return_value = res_val
    mock_res_val_get_llm.return_value = mock_res_val_llm

    # 6. Response agent response
    mock_resp_llm = MagicMock()
    resp_res = MagicMock()
    resp_res.content = "The total revenue across regions is $100,000."
    mock_resp_llm.invoke.return_value = resp_res
    mock_resp_get_llm.return_value = mock_resp_llm

    # Compile and invoke
    memory_checkpointer = MemorySaver()
    app = graph.compile(checkpointer=memory_checkpointer)

    initial_state: DatavoxState = {
        "session_id": "session-e2e-1",
        "user_query": "What is total revenue?",
        "node_trace": [],
        "current_node": "start",
        "cached_found": False,
        "retry_count": 3,
        "schema_context": "",
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

    config = {"configurable": {"thread_id": "session-e2e-1"}}
    final_state = app.invoke(initial_state, config=config)

    assert final_state["final_response"] == "The total revenue across regions is $100,000."
    assert "intent_router" in final_state["node_trace"]
    assert "sql_agent" in final_state["node_trace"]
    assert "validation_agent" in final_state["node_trace"]
    assert "execute_agent" in final_state["node_trace"]
    assert "result_validator_agent" in final_state["node_trace"]
    assert "response_agent" in final_state["node_trace"]
