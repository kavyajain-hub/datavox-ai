import json
import logging
import re
from graph.state import DatavoxState
from config.llm import get_llm

logger = logging.getLogger(__name__)


def allowed_statements(sql: str) -> bool:
    """Check if SQL query does not contain forbidden statements."""
    if not sql:
        return False
    # Pattern looks for 'drop', 'delete', or 'truncate' as standalone words
    forbidden_pattern = r"\b(drop|delete|truncate|insert|update|alter|create|grant|revoke)\b"
    if re.search(forbidden_pattern, sql, re.IGNORECASE):
        return False
    return True


def validation_agent(state: DatavoxState) -> DatavoxState:
    """Validate generated SQL query for forbidden statements, semantic alignment, and schema context."""
    generated_sql = state.get('generated_sql')
    user_query = state.get('user_query', '')
    schema_context = state.get('schema_context', '')

    # Hard guardrail check for forbidden statements
    if not allowed_statements(generated_sql):
        logger.error("Hard failure: Forbidden SQL statement", extra={
            "generated_sql": generated_sql,
            "current_node": "validation_agent",
            "node_trace": state.get('node_trace', []) + ['validation_agent']
        })
        return {
            **state,
            "is_sql_valid": False,
            "current_node": "validation_agent",
            "node_trace": state.get('node_trace', []) + ['validation_agent'],
            "validation_error": "Forbidden SQL statement"
        }

    # LLM validation: semantic alignment and schema context
    prompt = f"""
        you are a validation agent and you check the following
        - generated sql query are semantically aligned with user query 
        - generated sql query are taking schema context
        
        user_query = {user_query}
        schema_context = {schema_context}
        generated_sql = {generated_sql}

        output format should be in json : {{"semantically_aligned": true, "taking_schema_context": true}}
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

        sem_aligned = str(parsed.get('semantically_aligned', '')).lower() == "true"
        schema_ok = str(parsed.get('taking_schema_context', '')).lower() == "true"

        if not sem_aligned:
            return {
                **state,
                "is_sql_valid": False,
                "current_node": "validation_agent",
                "node_trace": state.get('node_trace', []) + ['validation_agent'],
                "validation_error": "Failed because the query is not semantically aligned"
            }

        if not schema_ok:
            return {
                **state,
                "is_sql_valid": False,
                "current_node": "validation_agent",
                "node_trace": state.get('node_trace', []) + ['validation_agent'],
                "validation_error": "Failed because the query is not taking right schema"
            }

        return {
            **state,
            "is_sql_valid": True,
            "current_node": "validation_agent",
            "node_trace": state.get('node_trace', []) + ['validation_agent'],
            "validation_error": None
        }

    except Exception as e:
        return {
            **state,
            "is_sql_valid": False,
            "current_node": "validation_agent",
            "node_trace": state.get('node_trace', []) + ['validation_agent'],
            "validation_error": str(e)
        }
