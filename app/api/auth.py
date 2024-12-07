import mysql
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db_connection
from app.core.security import verify_password, create_access_token, verify_token
from app.db.models.User import UserLogin, UserResponse, UserCreate
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login")
async def login(user: UserLogin, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    users_service = AuthService(db)
    db_user = users_service.get_user_by_email(user.email)

    if db_user is None or not verify_password(user.password, db_user.get('password_hash')):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(data={"sub": db_user.get('name') + db_user.get('last_name')})

    return UserResponse(
        name=db_user.get('name'),
        last_name=db_user.get('last_name'),
        email=db_user.get('email'),
        token=token,
        message="Login realizado!"
    )


@router.post("/register", response_model=UserResponse)
async def create_new_user(user: UserCreate, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = AuthService(db)
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

# test endpoint
@router.get("/users")
async def get_users(db: mysql.connector.MySQLConnection = Depends(get_db_connection), token: str = Depends(verify_token)):
    try:
        users_service = AuthService(db)

        return users_service.get_users()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))