from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 13374
    aigateway_url: str = "http://localhost:8001"
    voiceservice_url: str = "http://localhost:8002"

    # Bearer token used by AgentManager for AI generation calls (admin-level key
    # with smart routing enabled — separate from per-agent gateway tokens)
    system_gateway_key: str = ""

    # X-Admin-Key header sent to AIGateway admin endpoints
    aigateway_admin_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
