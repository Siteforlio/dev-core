from pydantic import BaseModel


class ApiKeySetRequest(BaseModel):
    value: str


class ApiKeyStatus(BaseModel):
    key_name: str
    configured: bool
    updated_at: str | None = None
