from fastapi import APIRouter
from app.graph import company_queries
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
async def list_companies():
    companies = await company_queries.get_all_companies()
    return {"data": companies, "error": None}


@router.get("/{company_name}/rounds")
async def get_round_types(company_name: str):
    service = CompanyService(graph=company_queries)
    rounds = await service.get_round_types(company_name)
    return {"data": rounds, "error": None}
