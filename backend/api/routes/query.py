from fastapi import APIRouter, HTTPException, status, Depends

from backend.api.models.requests import QueryRequest
from backend.api.models.responses import QueryResultResponse
from backend.api.services.engine_registry import get_registry
from backend.deps.validation import validate_query_payload  # NEW

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResultResponse)
async def process_query(
    validated: QueryRequest = Depends(validate_query_payload),  # CHANGED
) -> QueryResultResponse:
    connection_string = validated.connection_string
    if not connection_string:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="connection_string is required",
        )

    try:
        engine = get_registry().get_engine(connection_string)
        result = engine.process_query(validated.query, top_k=validated.top_k)
        return QueryResultResponse.model_validate(result)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/history")
async def get_history(connection_string: str) -> dict:
    try:
        engine = get_registry().get_engine(connection_string)
        return {"history": engine.get_history()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
