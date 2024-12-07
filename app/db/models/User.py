from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    last_name: str
    email: EmailStr
    password: str

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