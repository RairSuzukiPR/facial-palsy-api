from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "facial-palsy-api"
    DATABASE_URL: str
    SECRET_KEY: str

    database_host: str
    database_port: str
    database_name: str
    database_user: str
    database_password: str

    class Config:
        env_file = ".env"

settings = Settings()
