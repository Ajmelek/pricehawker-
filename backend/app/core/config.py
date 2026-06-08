from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    cerebras_api_key: str
    rapidapi_key: str
    database_url: str
    app_env: str = "development"
    secret_key: str

    class Config:
        env_file = ".env"

settings = Settings()