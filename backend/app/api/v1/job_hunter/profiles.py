import io
import pdfplumber
import docx as python_docx
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.job_hunter.profile_service import ProfileService
from app.schemas.job_hunter import ProfileUpsertRequest, ResumeTextRequest

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".doc"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/job-hunter/profiles", tags=["job-hunter-profiles"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/me", response_model=dict)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = ProfileService(db)
    profile = await service.get_profile(user_id)
    if profile is None:
        return {"data": {"is_complete": False, "completion_score": 0, "missing_fields": []}, "error": None}
    return {
        "data": {
            "id": profile.id,
            "is_complete": profile.is_complete,
            "completion_score": profile.completion_score,
            "missing_fields": [],
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "city": profile.city,
            "country": profile.country,
            "linkedin_url": profile.linkedin_url,
            "github_url": profile.github_url,
            "skills": profile.skills or [],
            "work_experience": profile.work_experience or [],
            "education": profile.education or [],
            "projects": profile.projects or [],
        },
        "error": None,
    }


@router.put("/me", response_model=dict)
async def upsert_profile(
    body: ProfileUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = ProfileService(db)
    profile = await service.upsert_profile(user_id, body.model_dump())
    completeness = service.check_completeness(body.model_dump())
    return {
        "data": {
            "id": profile.id,
            "is_complete": profile.is_complete,
            "completion_score": profile.completion_score,
            "missing_fields": completeness["missing"],
        },
        "error": None,
    }


@router.post("/me/parse-resume", response_model=dict)
async def parse_resume(
    body: ResumeTextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    service = ProfileService(db)
    extracted = await service.parse_resume_text(body.text)
    return {"data": extracted, "error": None}


@router.post("/me/parse-resume-file", response_model=dict)
async def parse_resume_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: PDF, DOCX, TXT.")

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 5 MB.")

    if ext == ".pdf":
        text = ""
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    elif ext in (".docx", ".doc"):
        doc = python_docx.Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = raw.decode("utf-8", errors="ignore")

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the file.")

    service = ProfileService(db)
    extracted = await service.parse_resume_text(text)
    return {"data": extracted, "error": None}
