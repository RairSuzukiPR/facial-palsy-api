import mysql
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db_connection
from app.core.security import verify_password, create_access_token, verify_token
from app.db.models.User import UserLogin, UserResponse, UserCreate, UserEdit
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/login")
async def login(user: UserLogin, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = AuthService(db)
        db_user = users_service.get_user_by_email(user.email)

        if db_user is None or not verify_password(user.password, db_user.get('password_hash')):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token(data={"id": db_user.get('id'), "name": db_user.get('name') + db_user.get('last_name')})

        return UserResponse(
            id=db_user.get('id'),
            name=db_user.get('name'),
            last_name=db_user.get('last_name'),
            email=db_user.get('email'),
            token=token,
            message="Login realizado!",
            eyelid_surgery=db_user.get('eyelid_surgery'),
            nasolabial_fold=db_user.get('nasolabial_fold'),
            nasolabial_fold_only_paralyzed_side=db_user.get('nasolabial_fold_only_paralyzed_side'),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register", response_model=UserResponse)
async def create_new_user(user: UserCreate, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = AuthService(db)
        user_id = users_service.create_user(user)
        token = create_access_token(data={"id": user_id, "name": user.name + user.last_name})

        return UserResponse(
            id=user_id,
            name=user.name,
            last_name=user.last_name,
            email=user.email,
            message="Usuário criado com sucesso!",
            token=token,
            eyelid_surgery=user.eyelid_surgery,
            nasolabial_fold=user.nasolabial_fold,
            nasolabial_fold_only_paralyzed_side=user.nasolabial_fold_only_paralyzed_side,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/edit", response_model=UserResponse, dependencies=[Depends(verify_token)])
async def create_new_user(user: UserEdit, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    try:
        users_service = AuthService(db)
        user_id = users_service.edit_user(user)
        token = create_access_token(data={"id": user_id, "name": user.name + user.last_name})

        return UserResponse(
            id=user_id,
            name=user.name,
            last_name=user.last_name,
            email=user.email,
            message="Usuário editado com sucesso!",
            token=token,
            eyelid_surgery=user.eyelid_surgery,
            nasolabial_fold=user.nasolabial_fold,
            nasolabial_fold_only_paralyzed_side=user.nasolabial_fold_only_paralyzed_side,
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