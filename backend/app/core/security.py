import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
from app.core.exceptions import InvalidCredentialsError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _utcnow():
    return datetime.now(timezone.utc)


def create_access_token(user_id: str) -> str:
    expire = _utcnow() + timedelta(minutes=settings.jwt_access_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_extension_token(user_id: str) -> str:
    """Long-lived token for the Chrome extension (1 year). Stored in chrome.storage.local."""
    expire = _utcnow() + timedelta(days=365)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "ext"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "type": "refresh", "jti": str(uuid.uuid4())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["sub"]
    except JWTError:
        raise InvalidCredentialsError()


def decode_refresh_token_payload(token: str) -> dict:
    """
    Decode a refresh token and return the full payload dict.
    Raises InvalidCredentialsError if the token is invalid or not a refresh token.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise InvalidCredentialsError()
        return payload
    except JWTError:
        raise InvalidCredentialsError()
