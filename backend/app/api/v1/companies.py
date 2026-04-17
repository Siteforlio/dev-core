from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.graph import company_queries
from app.services.company_service import CompanyService
from app.core.security import decode_token

router = APIRouter(prefix="/companies", tags=["companies"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("")
async def list_companies(user_id: str = Depends(get_user_id)):
    companies = await company_queries.get_all_companies()
    return {"data": companies, "error": None}


@router.get("/{company_name}/rounds")
async def get_round_types(company_name: str, user_id: str = Depends(get_user_id)):
    service = CompanyService(graph=company_queries)
    rounds = await service.get_round_types(company_name)
    return {"data": rounds, "error": None}
