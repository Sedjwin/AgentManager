from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 13374
    aigateway_url: str = "http://localhost:8001"
    voiceservice_url: str = "http://localhost:8002"

    class Config:
        env_file = ".env"


settings = Settings()
