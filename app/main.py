from fastapi import FastAPI

from app.api import sessions
from app.api import users

app = FastAPI()


app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(users.router, prefix="/users", tags=["users"])

@app.get("/health-check")
def health_check():
    return {"status": "alive"}
