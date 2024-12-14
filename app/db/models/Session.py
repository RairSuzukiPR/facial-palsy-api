from typing import List, Literal
from pydantic import BaseModel

class NewSessionPayload(BaseModel):
    user_id: int

class ProcessSessionPayload(BaseModel):
    session_id: int

class SessionResult(BaseModel):
    session_id: int
    house_brackmann: Literal['Grau I (Normal)', 'Grau II (Paralisia Leve)', 'Grau III (Paralisia Moderada)', 'Grau IV (Paralisia Moderada-Severa)', 'Grau V (Paralisia Severa)', 'Grau VI (Paralisia Total)']
    sunnybrook: int
    photos: List[str]
    photos_with_poitns: List[str]
