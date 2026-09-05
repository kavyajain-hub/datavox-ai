import json
from graph.state import DatavoxState
from config.llm import get_llm


def result_validator_agent(state: DatavoxState) -> DatavoxState:
    """Validate executed SQL output against user query to ensure the data answers the question."""
    user_query = state.get('user_query', '')
    executed_sql_output = state.get('executed_sql_output')

    prompt = f"""
        You are a result validator. You verify whether the executed SQL query output
        meaningfully and correctly answers the user's query.

        User query: {user_query}
        Executed SQL output: {executed_sql_output}

        Output strictly in JSON format:
        {{
            "is_valid": true,
            "reason": "explanation of validity"
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
        is_valid = bool(parsed.get("is_valid", True))

        return {
            **state,
            "result_validator": is_valid,
            "current_node": "result_validator_agent",
            "node_trace": state.get("node_trace", []) + ['result_validator_agent'],
            "result_validator_error": None
        }
    except Exception as e:
        return {
            **state,
            "result_validator": False,
            "current_node": "result_validator_agent",
            "node_trace": state.get("node_trace", []) + ['result_validator_agent'],
            "result_validator_error": str(e)
        }