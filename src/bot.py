# bot.py
import os
from typing import Any, List, Optional, Tuple, Union

import aiofiles
from aiogoogle import Aiogoogle
from aiogoogle.auth.creds import ServiceAccountCreds
from aiogoogle.models import HTTPError as AiogoogleHttpError
from discord.ext import commands
from dotenv import load_dotenv
from numpy import random


def getenv_required(env: str) -> str:
    if env in os.environ:
        return os.environ[env]
    raise ValueError(f"Environment variable '{env}' needs to be set!")


DOTENV_PATH = os.path.join(os.path.dirname(__file__), os.pardir, ".env")
load_dotenv(DOTENV_PATH)
DISCORD_BOT_TOKEN = getenv_required("DISCORD_BOT_TOKEN")
CHARACTER_SHEET_HASH = getenv_required("CHARACTER_SHEET_HASH")
GOOGLE_APPLICATION_CREDENTIALS = getenv_required("GOOGLE_APPLICATION_CREDENTIALS")
CLAIMS_DIR = getenv_required("CLAIMS_DIR")

bot = commands.Bot(command_prefix="!")


class SheetNotFoundError(Exception):
    def __init__(self, sheet_title: str) -> None:
        super().__init__(f"Sheet with title '{sheet_title}' not found!")


async def setup_aiogoogle() -> Aiogoogle:
    creds = ServiceAccountCreds(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    aiog = Aiogoogle(service_account_creds=creds)
    # Notice this line. Here, Aiogoogle loads the service account key.
    await aiog.service_account_manager.detect_default_creds_source()
    return aiog


async def get_ability_by_name(
    aiog: Aiogoogle,
    sheets_service: Any,
    doc_id: str,
    sheet_title: str,
    ability_name: str,
    lowercast: bool = True,
) -> List[Tuple[str, int]]:
    req = sheets_service.spreadsheets.values.get(
        spreadsheetId=doc_id, range=sheet_title  # is doc_id required here?
    )
    if lowercast:
        req.url = (
            f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq"
            f"?tq=select+A+,+F+where+lower(A)+contains+'{ability_name.lower()}'"
            f"+limit+3&sheet={sheet_title}&tqx=out:csv"
        )
    else:
        req.url = (
            f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq"
            f"?tq=select+A+,+F+where+A+contains+'{ability_name}'"
            f"+limit+3&sheet={sheet_title}&tqx=out:csv"
        )
    try:
        res_csv = await aiog.as_service_account(
            req,
        )
    except AiogoogleHttpError as e:
        if e.res.status_code == 400:
            raise SheetNotFoundError(sheet_title)
        else:
            raise e

    # extract all names and values from the csv response
    name_value_pairs = []
    for line in res_csv.split("\n"):
        if len(line) == 0:
            continue
        name, value = line.replace('"', "").split(",")  # remove all "" and split at ,
        value = int(value)
        name_value_pairs.append((name, value))
    return name_value_pairs


async def write_claim(guild_id: int, author_id: int, sheet_title: str) -> None:
    guild_dir_path = os.path.join(CLAIMS_DIR, str(guild_id))
    # TODO use the below as soon as aiofiles v0.8.0 gets released
    # await aiofiles.os.makedirs(guild_dir_path, exist_ok=True)
    # For now use the following workaround to create the dirs
    try:
        await aiofiles.os.mkdir(CLAIMS_DIR)  # type: ignore[attr-defined]
    except FileExistsError:
        pass
    try:
        await aiofiles.os.mkdir(guild_dir_path)  # type: ignore[attr-defined]
    except FileExistsError:
        pass
    # Create the claim file
    author_file_path = os.path.join(guild_dir_path, str(author_id))
    async with aiofiles.open(author_file_path, "w") as f:
        await f.write(sheet_title)


async def read_claim(guild_id: int, author_id: int) -> Optional[str]:
    author_file_path = os.path.join(CLAIMS_DIR, str(guild_id), str(author_id))
    try:
        async with aiofiles.open(author_file_path, "r") as f:
            sheet_title = await f.read()
        return sheet_title
    except FileNotFoundError:
        return None


async def get_sheet_titles(
    aiog: Aiogoogle, sheets_service: Any, doc_id: str
) -> List[str]:
    req = sheets_service.spreadsheets.get(
        spreadsheetId=doc_id, fields=["sheets.properties.title"]
    )
    res = await aiog.as_service_account(
        req,
    )
    sheet_titles = [sheet["properties"]["title"] for sheet in res["sheets"]]
    return sheet_titles


@bot.event
async def on_ready() -> None:
    print("Bot has connected to Discord!")


@bot.event
async def on_error(event: str, *args: str, **kwargs: Any) -> None:
    with open("err.log", "a") as f:
        if event == "on_message":
            f.write(f"Unhandled message: {args[0]}\n")
        else:
            raise


@bot.command(name="claim", help="Bind a character sheet to your user")
async def claim(ctx: commands.Context, *args: str) -> Any:
    if len(args) != 1:
        return await ctx.send(
            "ERROR: Invalid number of arguments."
            " Please provide exactly one character sheet name!"
        )
    sheet_title = args[0]

    aiog = await setup_aiogoogle()
    async with aiog:
        sheets_service = await aiog.discover("sheets", "v4")
        sheet_titles = await get_sheet_titles(
            aiog, sheets_service, CHARACTER_SHEET_HASH
        )

    if sheet_title not in sheet_titles:
        return await ctx.send(
            f"ERROR: {sheet_title} is not a sheet in the"
            " configured character sheet document!"
        )
    # write the claim
    guild_id = ctx.message.guild.id
    author_id = ctx.message.author.id
    await write_claim(guild_id, author_id, sheet_title)
    return await ctx.send(
        f"{ctx.message.author} claimed the sheet with title {sheet_title}"
    )


async def check_impl(ctx: commands.Context, character_name: str, *args: str) -> Any:

    # Setup aiogoogle with sheets READ credentials
    aiog = await setup_aiogoogle()

    expression: List[Union[Tuple[str, int], str]] = []
    async with aiog:
        sheets_service = await aiog.discover("sheets", "v4")
        # First make sure that the character_name belongs to a valid sheet
        sheet_titles = await get_sheet_titles(
            aiog, sheets_service, CHARACTER_SHEET_HASH
        )
        if character_name not in sheet_titles:
            return await ctx.send(
                f"ERROR: character name '{character_name}' does not correspond to a valid"
                " sheet in the configured character document!"
            )

        for idx, arg in enumerate(args):
            if idx % 2 == 0:
                # Try to extract ability name and value
                name = arg
                # First try to find results with lowercasting the name
                name_value_pairs = await get_ability_by_name(
                    aiog,
                    sheets_service,
                    CHARACTER_SHEET_HASH,
                    character_name,
                    name,
                    lowercast=False,
                )
                if len(name_value_pairs) == 0:
                    # No results found, try again with lowercasting
                    name_value_pairs = await get_ability_by_name(
                        aiog,
                        sheets_service,
                        CHARACTER_SHEET_HASH,
                        character_name,
                        name,
                        lowercast=True,
                    )
                    if len(name_value_pairs) == 0:
                        # Still no result, now it is a hard error
                        return await ctx.send(f"ERROR: No ability matches '{name}'")
                if len(name_value_pairs) > 1:
                    return await ctx.send(
                        f"ERROR: Multiple abilities ({[it[0] for it in name_value_pairs]} ...)"
                        f" match '{name}'. Please be more specific,"
                        " e.g. by typing more out or using correct uppercase."
                    )
                name, value = name_value_pairs[0]
                value = int(value)
                expression.append((name, value))
            else:
                # Try to extract seperator
                sep = arg
                if sep == "+" or sep == "-":
                    expression.append(sep)
                else:
                    response = (
                        f"ERROR: {sep} is an invalid seperator."
                        " Valid seperators are '+' or '-'"
                    )
                    return await ctx.send(response)

                if idx == len(args) - 1:
                    response = "ERROR: expression {} ends with a seperator!".format(
                        ctx.message.content
                    )
                    return await ctx.send(response)

    if len(expression) == 0:
        return await ctx.send("Nothing to roll!")

    # Happy path
    plus = random.randint(1, 5)
    minus = random.randint(1, 5)

    if len(expression) == 1:
        assert isinstance(expression[0], tuple)
        name, value = expression[0]
        response = (
            f"**{character_name}** rolls 2 x {name} + d4 - d4 = "
            f"{2*value} + {plus} - {minus} = **{2*value + plus - minus}**"
        )
    else:
        response_first = ""
        response_second = ""
        result = plus - minus
        sep = "+"
        for idx, name_value_or_sep in enumerate(expression):
            if idx % 2 == 0:
                # name, value pair
                assert isinstance(name_value_or_sep, tuple)
                (name, value) = name_value_or_sep
                response_first += name
                response_second += "{}".format(value)
                if sep == "+":
                    result += value
                else:
                    result -= value
            else:
                # seperator
                assert isinstance(name_value_or_sep, str)
                sep = name_value_or_sep

                response_first += " {} ".format(sep)
                response_second += " {} ".format(sep)

        response = (
            f"**{character_name}** rolls {response_first} + d4 - d4 = "
            f"{response_second} + {plus} - {minus} = **{result}**"
        )
    await ctx.send(response)


@bot.command(name="check", help="Roll a value on your character sheet")
async def check(ctx: commands.Context, *args: str) -> Any:
    # Find out which character the author has claimed
    guild_id = ctx.message.guild.id
    author_id = ctx.message.author.id
    character_name = await read_claim(guild_id, author_id)
    if character_name is None:
        return await ctx.send(
            f"@{ctx.message.author} you have not claimed a character yet."
            " Please do so by using the '!claim (character name)' command"
        )
    return await check_impl(ctx, character_name, *args)


@bot.command(
    name="check_character",
    help="Roll a value on the character sheet of a given character",
)
async def check_character(ctx: commands.Context, *args: str) -> Any:
    if len(args) < 1:
        return await ctx.send("ERROR: too few arguments")
    character_name = args[0]
    args = args[1:]
    return await check_impl(ctx, character_name, *args)


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
