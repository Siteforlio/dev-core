import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.exceptions import InvalidCredentialsError, UserAlreadyExistsError


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        name: str,
        email: str,
        password: str,
        language_pref: str,
        consent_given: bool,
    ) -> User:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise UserAlreadyExistsError()
        user = User(
            id=str(uuid.uuid4()),
            name=name,
            email=email,
            hashed_password=hash_password(password),
            language_pref=language_pref,
            consent_given_at=datetime.now(timezone.utc).replace(tzinfo=None) if consent_given else None,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, email: str, password: str) -> dict:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()
        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "user": user,
        }
