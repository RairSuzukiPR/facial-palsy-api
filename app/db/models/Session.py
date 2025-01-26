from typing import List, Literal
from pydantic import BaseModel
import datetime

class NewSessionPayload(BaseModel):
    user_id: int

class ProcessSessionPayload(BaseModel):
    session_id: int

class SessionResult(BaseModel):
    session_id: int
    house_brackmann: str
    sunnybrook: str
    eyes_simetry: int
    eyebrows_simetry: int
    mouth_simetry: int
    chin_simetry: int
    eyes_synkinesis: bool
    eyebrows_synkinesis: bool
    mouth_synkinesis: bool
    processed_at: datetime.datetime
    photos: List[str]