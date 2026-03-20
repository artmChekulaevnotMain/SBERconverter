from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

class AppSettings(BaseSettings):
    app_host: str = Field(validation_alias="APP_HOST", default="0.0.0.0")
    app_port: int = Field(validation_alias="APP_PORT", default=8000)
