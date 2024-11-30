import mysql
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db_connection
from app.core.security import verify_password, create_access_token
from app.db.models.User import UserLogin
from app.services.users_service import UsersService

router = APIRouter()


@router.post("/login")
async def login(user: UserLogin, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    users_service = UsersService(db)
    db_user = users_service.get_user_by_email(user.email)

    if db_user is None or not verify_password(user.password, db_user.get('password_hash')):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(data={"sub": db_user.get('name') + db_user.get('last_name')})
    return {"access_token": token}
