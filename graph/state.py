from typing import TypedDict, Optional, List

#define the Agent class
class DatavoxState(TypedDict):
    # use this to save each users session
    session_id : str                    # UUID (Universally Unique Identifiers)

    # cache questions outputs found
    cached_found : Optional[bool]     

    # current point of workflow
    current_node : Optional[str]

    # node trace
    node_trace : Optional[List[str]]

    # variable for DB tables - schema context
    schema_context : str

    # retry count variable
    retry_count : Optional[int]

    # maintain conversation history variable
    conversation_history:Optional[List[dict]]

    # variable for errors in intent router - json fails or any other error
    intent_router_error : Optional[str]
    intent_confidence_score : Optional[float]

    # user query variable
    user_query: str
    is_user_query_ambigous: Optional[bool]        # If true, lead back to clarificatory questions

    # sql_agent variables   
    generated_sql : Optional[str]
    sql_agent_error : Optional[str]

    # validation_agent variables
    is_sql_valid : Optional[bool]                  # If false, then can retry
    validation_error: Optional[str]

    # sql_execution variables
    executed_sql_output: Optional[List[dict]]       # though pd.DataFrame works locally, but in production we save the data as a list or rows
    sql_execution_error:Optional[str]

    # check to verify if the validator agent is doing job correctly
    result_validator:Optional[bool]
    result_validator_error:Optional[str]

    # final response variable
    final_response_error : Optional[str]
    final_response: Optional[str]



