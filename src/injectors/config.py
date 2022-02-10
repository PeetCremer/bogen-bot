from dependency_injector import containers, providers
from dotenv import find_dotenv
from pydantic import BaseSettings, Field


class BaseSettingsWithConfig(BaseSettings):
    class Config:
        env_file = find_dotenv()
        env_file_encoding = "utf-8"


class DiscordSettings(BaseSettingsWithConfig):
    discord_bot_token: str = Field(env="DISCORD_BOT_TOKEN")


class GoogleAPISettings(BaseSettingsWithConfig):
    google_application_credentials: str = Field(env="GOOGLE_APPLICATION_CREDENTIALS")
    character_sheet_hash: str = Field(env="CHARACTER_SHEET_HASH")


class DatabaseSettings(BaseSettingsWithConfig):
    claims_dir: str = Field(env="CLAIMS_DIR")


class Settings(BaseSettingsWithConfig):
    discord: DiscordSettings = DiscordSettings()
    gapi: GoogleAPISettings = GoogleAPISettings()
    db: DatabaseSettings = DatabaseSettings()


class Container(containers.DeclarativeContainer):
    config = providers.Configuration(pydantic_settings=[Settings()])


if __name__ == "__main__":
    container = Container()

    print(container.config.discord.discord_bot_token())
    print(container.config.gapi.google_application_credentials())
    print(container.config.gapi.character_sheet_hash())
    print(container.config.db.claims_dir())
