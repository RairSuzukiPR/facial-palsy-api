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
    sunnybrook: int
    hb_eyes_simetry: int
    hb_mouth_simetry: int
    sb_forehead_wrinkle_simetry: int
    sb_gentle_eye_closure_simetry: int
    sb_smile_simetry: int
    sb_snarl_simetry: int
    sb_lip_pucker_simetry: int
    eyes_synkinesis: bool
    eyebrows_synkinesis: bool
    mouth_synkinesis: bool
    processed_at: datetime.datetime
    photos: List[str]