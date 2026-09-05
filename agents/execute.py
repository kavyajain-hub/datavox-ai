from graph.state import DatavoxState
from sqlalchemy import text
from db.connection import get_engine


def execute_agent(state: DatavoxState) -> DatavoxState:
    """Execute generated SQL query against the configured database and return rows."""
    generated_sql = state.get('generated_sql')

    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(generated_sql))

            # Support both SQLAlchemy 2.0 result.mappings() and legacy/mock fetchall()
            if hasattr(result, "mappings") and not isinstance(result.mappings, dict):
                try:
                    all_rows = result.mappings().all()
                    rows = [dict(row) for row in all_rows]
                except (TypeError, AttributeError):
                    rows = [dict(getattr(r, "_mapping", getattr(r, "mapping", r))) for r in result.fetchall()]
            elif hasattr(result, "fetchall"):
                rows = [dict(getattr(r, "_mapping", getattr(r, "mapping", r))) for r in result.fetchall()]
            else:
                rows = []

        return {
            **state,
            "executed_sql_output": rows,
            "current_node": "execute_agent",
            "node_trace": state.get('node_trace', []) + ['execute_agent'],
            "sql_execution_error": None
        }

    except Exception as e:
        return {
            **state,
            "executed_sql_output": None,
            "current_node": "execute_agent",
            "node_trace": state.get('node_trace', []) + ['execute_agent'],
            "sql_execution_error": str(e)
        }