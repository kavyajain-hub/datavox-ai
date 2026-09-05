import json
from graph.state import DatavoxState
from rag.schema_retriever import retrieve_schema
from config.llm import get_llm


def sql_agent(state: DatavoxState) -> DatavoxState:
    """Generate SQL query based on user query, schema context, and conversation history."""
    retry_count = state.get('retry_count', 3)
    if state.get('validation_error') or state.get('sql_execution_error'):
        new_retry_count = retry_count - 1
    else:
        new_retry_count = retry_count

    user_query = state.get('user_query', '')
    history = state.get('conversation_history') or []
    formatted_text = '\n'.join(
        f"{item.get('role', 'user')}: {item.get('content', '')}"
        for item in history
    )

    schema_info = state.get('schema_context')
    if not schema_info:
        schema_info = retrieve_schema(user_query)

    prompt = f"""
        You are a data analyst that generates SQL queries based on user questions.

        **CRITICAL RULES:**
        - Only generate SELECT queries.
        - NEVER generate DELETE, DROP, ALTER, TRUNCATE, INSERT, or UPDATE queries.
        - Refer to the provided schema context and conversation history.

        Schema Context:
        {schema_info}

        Conversation History:
        {formatted_text}

        User Query:
        {user_query}

        Output strictly in JSON format: {{"sql": "SELECT ... FROM ..."}}
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
        generated_sql = parsed.get('sql', '').strip()

        # Clean any trailing markdown if the model included it inside sql value
        if generated_sql.startswith("```sql"):
            generated_sql = generated_sql[6:].strip()
        if generated_sql.endswith("```"):
            generated_sql = generated_sql[:-3].strip()

        return {
            **state,
            "generated_sql": generated_sql,
            "schema_context": schema_info,
            "current_node": "sql_agent",
            "node_trace": state.get('node_trace', []) + ['sql_agent'],
            "sql_agent_error": None,
            "retry_count": new_retry_count
        }

    except Exception as e:
        return {
            **state,
            "generated_sql": None,
            "schema_context": schema_info,
            "current_node": "sql_agent",
            "node_trace": state.get('node_trace', []) + ['sql_agent'],
            "sql_agent_error": str(e),
            "retry_count": new_retry_count
        }