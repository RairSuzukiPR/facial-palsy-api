from fastapi import FastAPI

from app.api import sessions, auth, images

app = FastAPI()

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(images.router, prefix="/images", tags=["sessions"])

@app.get("/health-check")
def health_check():
    return {"status": "alive"}
