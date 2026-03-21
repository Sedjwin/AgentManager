from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aigateway_url: str = "http://localhost:8001"
    voiceservice_url: str = "http://localhost:8002"
    database_url: str = "sqlite+aiosqlite:///./data/agentmanager.db"

    model_config = {"env_file": ".env"}


settings = Settings()
