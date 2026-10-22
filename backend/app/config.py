from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = 'mysql+pymysql://campustrack:change-me@localhost:3306/campustrack?charset=utf8mb4'
    frontend_origin: str = 'http://localhost:5173'
    secure_cookies: bool = False
    cookie_samesite: Literal['lax','none'] = 'lax'
    sms_enabled: bool = False
    sms_college_approved: bool = False
    sms_provider_url: str = ''
    sms_api_key: str = ''
    sms_sender_id: str = ''
    sms_dlt_entity_id: str = ''
    session_hours: int = 8
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
settings = Settings()
