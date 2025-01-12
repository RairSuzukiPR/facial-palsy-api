from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    last_name: str
    email: EmailStr
    password: str
    eyelid_surgery: bool
    nasolabial_fold: bool
    nasolabial_fold_only_paralyzed_side: bool

class UserResponse(BaseModel):
    id: int
    name: str
    last_name: str
    email: EmailStr
    message: str
    token: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str