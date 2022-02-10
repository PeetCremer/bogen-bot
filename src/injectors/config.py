from typing import Any, Dict

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject
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


class SomeContainer(containers.DeclarativeContainer):
    config = providers.Configuration()


class Application(containers.DeclarativeContainer):
    config = providers.Configuration(pydantic_settings=[Settings()], strict=True)
    some = providers.Container(SomeContainer, config=config.discord)


@inject
def main(
    discord_bot_token: str = Provide[Application.config.discord.discord_bot_token],
    some_config: Dict[str, Any] = Provide[Application.some.config],
) -> None:
    print(type(discord_bot_token))
    print(discord_bot_token)

    print(type(some_config))
    print(some_config)


if __name__ == "__main__":
    application = Application()
    application.wire(modules=[__name__])

    print(type(application.config.discord))

    main()
