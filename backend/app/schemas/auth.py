from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    language_pref: str = "en"
    consent_given: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    name: str
    language_pref: str


class AuthResponse(BaseModel):
    data: TokenResponse
    error: None = None
