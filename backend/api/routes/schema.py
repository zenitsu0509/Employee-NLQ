from fastapi import APIRouter, HTTPException, status

from backend.api.models.responses import SchemaResponse
from backend.api.services.engine_registry import get_registry

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get("", response_model=SchemaResponse)
async def get_schema(connection_string: str) -> SchemaResponse:
    try:
        engine = get_registry().get_engine(connection_string)
        schema = engine.refresh_schema()
        return SchemaResponse.model_validate(schema)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
