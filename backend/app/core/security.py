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


def create_refresh_token(user_id: str) -> str:
    expire = _utcnow() + timedelta(days=settings.jwt_refresh_expire_days)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "refresh"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["sub"]
    except JWTError:
        raise InvalidCredentialsError()
