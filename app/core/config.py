from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "facial-palsy-api"
    DATABASE_URL: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
