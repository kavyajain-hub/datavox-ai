import logging
from graph.state import DatavoxState

logger = logging.getLogger(__name__)


def clarify_agent(state: DatavoxState) -> DatavoxState:
    """Terminal node for asking clarification when query is ambiguous."""
    return {
        **state,
        "final_response": "Could you please clarify your question with more details?",
        "current_node": "clarify_agent",
        "node_trace": state.get('node_trace', []) + ["clarify_agent"]
    }


def escalate_agent(state: DatavoxState) -> DatavoxState:
    """Terminal node for escalating when retries are exhausted, forbidden query detected, or API failure."""
    from config.llm import user_provider_ctx
    from config.settings import get_settings

    error = (
        state.get('intent_router_error') or
        state.get('validation_error') or
        state.get('sql_execution_error') or
        "Unknown error"
    )
    logger.error("Escalation triggered", extra={
        "user_query": state.get('user_query'),
        "error": error,
        "node_trace": state.get('node_trace')
    })
    error_str = str(error)
    active_prov = user_provider_ctx.get() or get_settings().llm_provider or "gemini"
    is_openai = (active_prov.lower() == "openai")
    provider_name = "OpenAI" if is_openai else "Google Gemini"

    if "429" in error_str or "quota" in error_str.lower() or "resource_exhausted" in error_str.lower() or "insufficient_quota" in error_str.lower():
        if is_openai:
            msg = (
                "OpenAI Quota Exceeded (429): Your OpenAI account has exhausted its API credit balance or requires billing setup (platform.openai.com/billing). "
                "To continue querying for free, click 'API Key' in the top right, switch to Google Gemini, or click 'Clear' to use the server default."
            )
        else:
            msg = (
                f"{provider_name} Rate Limit / Quota Exceeded (429): The API key has reached its request quota limit. "
                "Please wait a moment and try again, enter a new key in 'API Key' settings, or click 'Clear' to use the server default."
            )
    elif "403" in error_str or "permission_denied" in error_str.lower() or "denied access" in error_str.lower():
        msg = (
            f"{provider_name} Permission Denied (403): The project or API key was denied access. "
            "Please click the 'API Key' button in the top right and click 'Clear' to use the server default, or enter a new valid API key."
        )
    elif "api key" in error_str.lower() or "auth" in error_str.lower() or "401" in error_str:
        msg = f"Invalid {provider_name} API key or unauthorized access (401). Please click 'API Key' in the top right to enter a valid key."
    elif "unreachable" in error_str.lower() or "connection" in error_str.lower() or "timeout" in error_str.lower():
        msg = f"Unable to reach {provider_name} API. Please check your internet connection or try again in a few seconds."
    else:
        msg = f"We encountered an issue processing your request: {error_str}"

    return {
        **state,
        "final_response": msg,
        "current_node": "escalate_agent",
        "node_trace": state.get('node_trace', []) + ['escalate_agent']
    }