import mysql
from fastapi import APIRouter, Depends

from app.api.deps import get_db_connection
from app.services.users_service import UsersService

router = APIRouter()

@router.get("/")
async def get_users(db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = UsersService(db)
        return users_service.get_users()
    except Exception as e:
        return {"error": str(e)}, 400
