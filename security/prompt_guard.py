import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# Comprehensive prompt injection and SQL attack patterns
_INJECTION_PATTERNS = [
    # Prompt injection attempts
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now",
    r"forget\s+everything",
    r"disregard\s+(all\s+)?(prior|previous|above)",
    r"act\s+as\s+(a\s+)?",
    r"pretend\s+(you('re|\s+are)\s+)",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*",
    # SQL injection / dangerous statements
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bTRUNCATE\b",
    r"\bUNION\s+SELECT\b",
    r"\bINSERT\s+INTO\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\bALTER\s+TABLE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC(\s|UTE)\b",
    r"\bxp_cmdshell\b",
    r";\s*--",
    r"'\s*OR\s+'1'\s*=\s*'1",
]

_COMPILED_PATTERN = re.compile(
    r'(' + '|'.join(_INJECTION_PATTERNS) + r')',
    flags=re.IGNORECASE
)


def check_prompt(user_query: str) -> Tuple[bool, List[str]]:
    """Check query against comprehensive prompt injection and SQL attack patterns.

    Uses a fast regex blocklist instead of an LLM call to avoid doubling
    latency — the downstream validation_agent already performs LLM-based
    semantic SQL validation.
    """
    match = _COMPILED_PATTERN.search(user_query)
    if match:
        logger.warning(f"Prompt guard blocked query: matched '{match.group()}'")
        return (False, [f"Forbidden: Found '{match.group()}' in query"])

    return (True, [])

