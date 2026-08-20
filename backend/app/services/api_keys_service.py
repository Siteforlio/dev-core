"""
Service for managing user API keys stored in the database.
Keys are encrypted at rest using Fernet symmetric encryption.
"""
import json
import uuid
from cryptography.fernet import Fernet
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.pg.user_settings import UserApiKey

# All recognised API key names — anything else is rejected
VALID_KEY_NAMES: set[str] = {
    # Required
    "deepseek_api_key",
    "deepgram_api_key",
    # LLM providers
    "anthropic_api_key",
    "gemini_api_key",
    "groq_api_key",
    "openai_api_key",
    # Avatar
    "heygen_api_key",
    "simli_api_key",
    # Overlay tools
    "judge0_api_key",
    "serp_api_key",
    # Job boards
    "adzuna_app_id",
    "adzuna_api_key",
    "reed_api_key",
    "scrapfly_key",
}

LLM_KEYS: set[str] = {
    "deepseek_api_key",
    "anthropic_api_key",
    "gemini_api_key",
    "groq_api_key",
    "openai_api_key",
}

# At least one LLM key is required for the app to function
REQUIRED_KEYS: set[str] = set()  # No single key is individually required


def _fernet() -> Fernet:
    key = settings.job_hunter_encryption_key
    if not key:
        raise ValueError("JOB_HUNTER_ENCRYPTION_KEY is not configured — cannot encrypt API keys")
    return Fernet(key.encode())


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


class ApiKeysService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_status(self, user_id: str) -> list[dict]:
        """Return configuration status for all known keys (never returns values)."""
        result = await self.db.execute(
            select(UserApiKey).where(UserApiKey.user_id == user_id)
        )
        rows = {r.key_name: r for r in result.scalars().all()}
        out = []
        for name in sorted(VALID_KEY_NAMES):
            row = rows.get(name)
            out.append({
                "key_name": name,
                "configured": row is not None,
                "required": name in REQUIRED_KEYS,
                "updated_at": row.updated_at.isoformat() if row else None,
            })
        return out

    async def set_key(self, user_id: str, key_name: str, value: str) -> None:
        """Upsert an API key (encrypted at rest)."""
        if key_name not in VALID_KEY_NAMES:
            raise ValueError(f"Unknown API key: {key_name}")
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.key_name == key_name,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.encrypted_value = _encrypt(value)
            from datetime import datetime, timezone
            row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            row = UserApiKey(
                id=str(uuid.uuid4()),
                user_id=user_id,
                key_name=key_name,
                encrypted_value=_encrypt(value),
            )
            self.db.add(row)
        await self.db.commit()

    async def delete_key(self, user_id: str, key_name: str) -> None:
        """Remove an API key."""
        await self.db.execute(
            delete(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.key_name == key_name,
            )
        )
        await self.db.commit()

    async def get_decrypted(self, user_id: str, key_name: str) -> str | None:
        """Get a decrypted API key value (for internal use by other services)."""
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.key_name == key_name,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return _decrypt(row.encrypted_value)

    async def get_all_decrypted(self, user_id: str) -> dict[str, str]:
        """Get all decrypted API keys for a user (for internal use by services)."""
        result = await self.db.execute(
            select(UserApiKey).where(UserApiKey.user_id == user_id)
        )
        return {r.key_name: _decrypt(r.encrypted_value) for r in result.scalars().all()}
