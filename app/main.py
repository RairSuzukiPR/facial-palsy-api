from fastapi import FastAPI

from app.api import sessions, users, auth

app = FastAPI()

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
# TODO: jogar pra auth?
app.include_router(users.router, prefix="/users", tags=["users"])

@app.get("/health-check")
def health_check():
    return {"status": "alive"}
