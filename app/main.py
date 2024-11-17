from fastapi import FastAPI

from app.api import sessions

app = FastAPI()


app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
@app.get("/health-check")
def health_check():
    return {"status": "alive"}
