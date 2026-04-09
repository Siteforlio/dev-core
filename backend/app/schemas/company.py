from pydantic import BaseModel


class CompanyOut(BaseModel):
    name: str
    industry: str


class CompanyListResponse(BaseModel):
    data: list[CompanyOut]
    error: None = None


class RoundTypesResponse(BaseModel):
    data: list[str]
    error: None = None
