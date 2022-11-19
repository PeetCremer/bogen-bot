import os

from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds
from dependency_injector import containers, providers
from dotenv import find_dotenv
from pydantic import BaseSettings, Field


class BaseConfig(BaseSettings):
    class Config:
        env_file = find_dotenv()
        env_file_encoding = "utf-8"


class DiscordConfig(BaseConfig):
    discord_bot_token: str = Field(env="DISCORD_BOT_TOKEN")


class GoogleAPIConfig(BaseConfig):
    google_application_credentials: str = Field(env="GOOGLE_APPLICATION_CREDENTIALS")
    character_sheet_hash: str = Field(env="CHARACTER_SHEET_HASH")


class DatabaseConfig(BaseConfig):
    claims_dir: str = Field(env="CLAIMS_DIR")


class AppConfig(BaseConfig):
    discord: DiscordConfig = DiscordConfig()
    gapi: GoogleAPIConfig = GoogleAPIConfig()
    db: DatabaseConfig = DatabaseConfig()


async def init_aiog(google_application_credentials: str) -> Aiogoogle:
    # Explicitly set credentials, since loading them from .env files
    # does not set them as environment variable, but google API wants
    # it to be explicitly set
    os.environ.setdefault(
        "GOOGLE_APPLICATION_CREDENTIALS", google_application_credentials
    )
    creds = ServiceAccountCreds(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    aiog = Aiogoogle(service_account_creds=creds)
    # Notice this line. Here, Aiogoogle loads the service account key.
    await aiog.service_account_manager.detect_default_creds_source()
    yield aiog


class AppConfigContainer(containers.DeclarativeContainer):
    config = providers.Configuration(pydantic_settings=[AppConfig()], strict=True)
    aiog = providers.Resource(init_aiog, config.gapi.google_application_credentials)
