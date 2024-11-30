from fastapi import APIRouter, File, UploadFile, Depends

from app.core.security import verify_token
from app.services.sessions_service import SessionService

router = APIRouter(
    dependencies=[Depends(verify_token)]
)

@router.post("/classify-img")
async def upload_file(file: UploadFile = File(...), facialExpression: str = File(...)):
    try:
        session_service = SessionService()
        return session_service.classify_image(file)
    except Exception as e:
        return {"error": str(e)}, 400
