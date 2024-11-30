import mysql
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_db_connection
from app.core.security import create_access_token

from app.db.models.User import UserCreate, UserResponse
from app.services.users_service import UsersService

router = APIRouter()

@router.get("/")
async def get_users(db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = UsersService(db)

        return users_service.get_users()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/register", response_model=UserResponse)
async def create_new_user(user: UserCreate, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = UsersService(db)
        users_service.create_user(user)
        token = create_access_token(data={"sub": user.name + user.last_name})

        return UserResponse(
            name=user.name,
            last_name=user.last_name,
            email=user.email,
            message="Usuário criado com sucesso!",
            token=token
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
