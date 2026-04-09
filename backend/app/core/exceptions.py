from fastapi import Request
from fastapi.responses import JSONResponse


class DevCoreException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidCredentialsError(DevCoreException):
    def __init__(self):
        super().__init__("INVALID_CREDENTIALS", "Invalid email or password", 401)


class UserAlreadyExistsError(DevCoreException):
    def __init__(self):
        super().__init__("USER_ALREADY_EXISTS", "An account with this email already exists", 409)


class SessionNotFoundError(DevCoreException):
    def __init__(self):
        super().__init__("SESSION_NOT_FOUND", "Interview session not found", 404)


class RoundNotFoundError(DevCoreException):
    def __init__(self):
        super().__init__("ROUND_NOT_FOUND", "Interview round not found", 404)


class UserNotFoundError(DevCoreException):
    def __init__(self):
        super().__init__("USER_NOT_FOUND", "User not found", 404)


def register_exception_handlers(app):
    @app.exception_handler(DevCoreException)
    async def devcore_exception_handler(request: Request, exc: DevCoreException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"data": None, "error": {"code": exc.code, "message": exc.message}}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"data": None, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}}
        )
