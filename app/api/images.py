import mysql
from fastapi import APIRouter, File, UploadFile, Depends

from app.api.deps import get_db_connection
from app.core.security import verify_token
from app.services.images_service import ImagesService

router = APIRouter(
    dependencies=[Depends(verify_token)]
)

@router.post("/upload")
async def upload_image(file: UploadFile = File(...), facial_expression: str = File(...), session_id: str = File(...), db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        images_service = ImagesService(db)
        result = images_service.classify_image(file)

        images_service.insert_images_db(result["image"], session_id, 'img_url?', facial_expression, False)
        images_service.insert_images_db(result["image_with_points"], session_id, 'img_url?', facial_expression, True)

        return
    except Exception as e:
        return {"error": str(e)}, 400
