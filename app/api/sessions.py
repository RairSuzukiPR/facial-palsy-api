import shutil
from fastapi import APIRouter, File, UploadFile
# from app.schemas.session import Session
from app.services.sessions_service import SessionService

router = APIRouter()

@router.post("/classify-img")
async def upload_file(file: UploadFile = File(...), facialExpression: str = File(...)):
    try:
        session_service = SessionService()
        return session_service.classify_image(file)
    except Exception as e:
        return {"error": str(e)}, 400

@router.get("/test")
async def test():
    session_service = SessionService()
    return session_service.classify_image()