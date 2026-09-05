from graph.state import DatavoxState
from config.llm import get_llm


def response_agent(state: DatavoxState) -> DatavoxState:
    """Synthesize a natural language, communicative response for the user from SQL execution output."""
    user_query = state.get('user_query', '')
    executed_sql_output = state.get('executed_sql_output')

    prompt = f"""
        You are a helpful and articulate data assistant.
        Provide a clear, conversational, and insightful summary answering the user's question
        based strictly on the executed SQL query output.

        User Query: {user_query}
        Executed SQL Output: {executed_sql_output}

        Keep your tone professional, communicative, and helpful.
    """
    try:
        llm = get_llm(temperature=0)
        response = llm.invoke(prompt)
        final_response = response.content.strip()

        return {
            **state,
            "final_response": final_response,
            "current_node": "response_agent",
            "node_trace": state.get("node_trace", []) + ['response_agent'],
            "final_response_error": None
        }
    except Exception as e:
        return {
            **state,
            "final_response": "I retrieved the data but encountered an issue formatting the final response.",
            "current_node": "response_agent",
            "node_trace": state.get("node_trace", []) + ['response_agent'],
            "final_response_error": str(e)
        }