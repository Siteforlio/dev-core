"""
API key management routes.
Users configure their provider API keys here — stored encrypted in the database.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.api_keys import ApiKeySetRequest
from app.services.api_keys_service import ApiKeysService, VALID_KEY_NAMES

router = APIRouter(prefix="/settings/api-keys", tags=["settings"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/status")
async def get_status(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Return which API keys are configured (never returns actual values)."""
    service = ApiKeysService(db)
    keys = await service.get_status(user_id)
    return {"data": {"keys": keys}, "error": None}


@router.put("/{key_name}")
async def set_key(
    key_name: str,
    body: ApiKeySetRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Set or update an API key."""
    if key_name not in VALID_KEY_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown API key: {key_name}")
    if not body.value.strip():
        raise HTTPException(status_code=400, detail="API key value cannot be empty")
    service = ApiKeysService(db)
    await service.set_key(user_id, key_name, body.value.strip())
    return {"data": {"key_name": key_name, "configured": True}, "error": None}


@router.delete("/{key_name}")
async def delete_key(
    key_name: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Remove an API key."""
    if key_name not in VALID_KEY_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown API key: {key_name}")
    service = ApiKeysService(db)
    await service.delete_key(user_id, key_name)
    return {"data": {"key_name": key_name, "configured": False}, "error": None}
