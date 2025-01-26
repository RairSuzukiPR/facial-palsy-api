import os
import mysql
from fastapi import APIRouter, Depends, HTTPException
from collections import defaultdict

from app.api.deps import get_db_connection
from app.core.security import verify_token
from app.db.models.Session import NewSessionPayload, ProcessSessionPayload, SessionResult
from app.services.auth_service import AuthService
from app.services.sessions_service import SessionService

router = APIRouter(
    dependencies=[Depends(verify_token)]
)

@router.post("/new_session")
async def new_session(data: NewSessionPayload, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        session_service = SessionService(db)
        return session_service.new_session(data.user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/process")
async def process_session(data: ProcessSessionPayload, db: mysql.connector.MySQLConnection = Depends(get_db_connection), user: dict = Depends(verify_token)):
    try:
        session_service = SessionService(db)
        auth_service = AuthService(db)

        user = auth_service.get_user_by_id(user.get('id'))
        return session_service.process_session(user, data.session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions")
async def get_users(db: mysql.connector.MySQLConnection = Depends(get_db_connection), user: dict = Depends(verify_token)):
    try:
        session_service = SessionService(db)
        data =  session_service.get_sessions(user.get('id'))

        grouped = defaultdict(lambda: {
            'session_id': None,
            'house_brackmann': None,
            'sunnybrook': None,
            'eyes_simetry': None,
            'eyebrows_simetry': None,
            'mouth_simetry': None,
            'chin_simetry': None,
            'eyes_synkinesis': None,
            'eyebrows_synkinesis': None,
            'mouth_synkinesis': None,
            'processed_at': None,
            'photos': []
        })

        for item in data:
            session_id = item['session_id']
            grouped[session_id]['session_id'] = item['session_id']
            grouped[session_id]['house_brackmann'] = item['house_brackmann']
            grouped[session_id]['sunnybrook'] = item['sunnybrook']
            grouped[session_id]['eyes_simetry'] = item['eyes_simetry']
            grouped[session_id]['eyebrows_simetry'] = item['eyebrows_simetry']
            grouped[session_id]['mouth_simetry'] = item['mouth_simetry']
            grouped[session_id]['chin_simetry'] = item['chin_simetry']
            grouped[session_id]['eyes_synkinesis'] = item['eyes_synkinesis']
            grouped[session_id]['eyebrows_synkinesis'] = item['eyebrows_synkinesis']
            grouped[session_id]['mouth_synkinesis'] = item['mouth_synkinesis']
            grouped[session_id]['processed_at'] = item['processed_at']
            # grouped[session_id]['photos'].append(item['photo_id'])
            # photo_path = os.path.join(os.getcwd(), f"app/assets/{item['photo_id']}.jpg")
            #
            # base64_image = file_to_base64(photo_path)
            # if base64_image:
            #     grouped[session_id]['photos'].append(base64_image)

        return [SessionResult(**group) for group in grouped.values()]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/session-images")
async def get_session_images(session_id: int, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        session_service = SessionService(db)
        result = session_service.get_session_images(session_id)

        images = []
        for item in result:
            photo_path = os.path.join(os.getcwd(), f"app/assets/{item['photo_id']}.jpg")
            base64_image = session_service.file_to_base64(photo_path, compression_level=30)
            if base64_image:
                images.append("data:image/jpeg;base64," + base64_image)

        return images
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
