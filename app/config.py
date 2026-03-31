from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aigateway_url: str = "http://localhost:8001"
    voiceservice_url: str = "http://localhost:8002"
    voiceservice_stt_timeout_s: float = 120.0
    voiceservice_tts_timeout_s: float = 600.0
    agentmanager_url: str = "http://localhost:8003"  # self-reference for ask-agent tool
    usermanager_url: str = "http://localhost:8005"
    usermanager_service_key: str = "change-me-service-key"
    toolgateway_url: str = "http://localhost:8006"
    toolgateway_service_key: str = ""  # UserManager admin API key used to call ToolGateway
    database_url: str = "sqlite+aiosqlite:///./data/agentmanager.db"
    webservice_files_url: str = "https://chip.iampc.uk:13383/files"

    model_config = {"env_file": ".env"}


settings = Settings()
