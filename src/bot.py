# bot.py
import os
from typing import Any, List, Tuple, Union

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

bot = commands.Bot(command_prefix="!")


class SheetNotFoundError(Exception):
    def __init__(self, sheet_title: str) -> None:
        super().__init__(f"Sheet with title '{sheet_title}' not found!")


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


async def get_ability_by_name(
    aiog: Aiogoogle,
    sheets_service: Any,
    doc_id: str,
    sheet_title: str,
    ability_name: str,
) -> List[Tuple[str, int]]:
    req = sheets_service.spreadsheets.values.get(
        spreadsheetId=doc_id, range=sheet_title
    )
    req.url = (
        f"https://docs.google.com/spreadsheets/d/{CHARACTER_SHEET_HASH}/gviz/tq"
        f"?tq=select+A+,+F+where+lower(A)+contains+'{ability_name.lower()}'"
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


@bot.command(name="check", help="Roll a value on the character sheet")
async def check(ctx: commands.Context, *args: str) -> Any:
    # Setup aiogoogle with sheets READ credentials
    aiog = await setup_aiogoogle()

    # Quick hack to make rolling for everyone work
    character_name = args[0]
    args = args[1:]

    expression: List[Union[Tuple[str, int], str]] = []
    async with aiog:
        sheets_service = await aiog.discover("sheets", "v4")
        for idx, arg in enumerate(args):
            if idx % 2 == 0:
                # Try to extract ability name and value
                name = arg
                name_value_pairs = await get_ability_by_name(
                    aiog, sheets_service, CHARACTER_SHEET_HASH, character_name, name
                )  # TODO more generic
                if len(name_value_pairs) == 0:
                    return await ctx.send(f"ERROR: No ability matches '{name}'")
                if len(name_value_pairs) > 1:
                    return await ctx.send(
                        f"ERROR: Multiple abilities ({[it[0] for it in name_value_pairs]} ...)"
                        f" match '{name}'. Please be more specific!"
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
        response = "Rolling 2 x {} + d4 - d4 = {} + {} - {} = **{}**".format(
            name, 2 * value, plus, minus, 2 * value + plus - minus
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

        response = "Rolling {} + d4 - d4 = {} + {} - {} = **{}**".format(
            response_first, response_second, plus, minus, result
        )
    await ctx.send(response)


async def setup_aiogoogle() -> Aiogoogle:
    creds = ServiceAccountCreds(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    aiog = Aiogoogle(service_account_creds=creds)
    # Notice this line. Here, Aiogoogle loads the service account key.
    await aiog.service_account_manager.detect_default_creds_source()
    return aiog


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
