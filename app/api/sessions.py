import mysql
from fastapi import APIRouter, Depends, HTTPException

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
        # SessionResult()
        return session_service.process_session(user, data.session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
