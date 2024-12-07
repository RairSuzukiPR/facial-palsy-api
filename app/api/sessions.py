import mysql
from fastapi import APIRouter, Depends

from app.api.deps import get_db_connection
from app.core.security import verify_token
from app.services.sessions_service import SessionService

router = APIRouter(
    dependencies=[Depends(verify_token)]
)

@router.post("/new_session")
async def new_session(user_id: str, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        session_service = SessionService(db)
        return session_service.new_session(user_id)
    except Exception as e:
        return {"error": str(e)}, 400
