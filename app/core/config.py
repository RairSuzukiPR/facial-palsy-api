from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "facial-palsy-api"
    DATABASE_URL: str
    database_host: str
    database_port: str
    database_name: str
    database_user: str
    database_password: str

    SECRET_KEY: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    class Config:
        env_file = ".env"

    def generate_database_url(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

settings = Settings()
