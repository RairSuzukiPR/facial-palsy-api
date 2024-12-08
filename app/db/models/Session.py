from pydantic import BaseModel

class NewSessionPayload(BaseModel):
    user_id: int
