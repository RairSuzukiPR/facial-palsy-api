from typing import List, Literal
from pydantic import BaseModel

class NewSessionPayload(BaseModel):
    user_id: int

class ProcessSessionPayload(BaseModel):
    session_id: int

class SessionResult(BaseModel):
    session_id: int
    house_brackmann: Literal['I', 'II', 'III', 'IV', 'V']
    sunnybrook: int
    photos: List[str]
    photos_with_poitns: List[str]
