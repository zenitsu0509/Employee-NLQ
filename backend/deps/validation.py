from fastapi import HTTPException, status, Body
from backend.api.models.requests import QueryRequest
from backend.utils.sanitizer import (
    clean_input,
    is_too_long,
    has_suspicious_patterns,
    detect_url,
    DEFAULT_MAX_LENGTH,
)


def validate_query_payload(payload: QueryRequest = Body(...)) -> QueryRequest:
    """
    FastAPI dependency to sanitize and validate QueryRequest coming from JSON body.
    Raises HTTPException on invalid input. Returns sanitized payload.
    """
    # Clean input
    cleaned = clean_input(payload.query if payload.query is not None else "")
    if cleaned == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty after trimming whitespace.",
        )

    # Length check
    if is_too_long(cleaned, DEFAULT_MAX_LENGTH):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Query is too long (>{DEFAULT_MAX_LENGTH} chars).",
        )

    # Suspicious pattern check
    suspicious, match = has_suspicious_patterns(cleaned)
    if suspicious:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query contains suspicious token: '{match}'.",
        )

    # (Optional) If we detect URLs, we can decide to remove them or error out.
    # For now, we simply detect them and allow. If desired, uncomment:
    # if detect_url(cleaned):
    #     cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned).strip()

    # Put cleaned query back in payload and return
    payload.query = cleaned
    return payload
