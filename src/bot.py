# bot.py
import asyncio
import json
import os
from typing import Any, Awaitable, Dict, List, Optional, Tuple, Union

import aiofiles
import numpy as np
from aiogoogle import Aiogoogle
from aiogoogle.models import HTTPError as AiogoogleHttpError
from dependency_injector.wiring import Provide, inject
from discord.ext import commands

from app_config import AppConfigContainer

bot = commands.Bot(command_prefix="!")


class SheetNotFoundError(Exception):
    def __init__(self, sheet_title: str) -> None:
        super().__init__(f"Sheet with title '{sheet_title}' not found!")


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
            f"?tq=select+A+,+G+where+lower(A)+contains+'{ability_name.lower()}'"
            f"+limit+3&sheet={sheet_title}&tqx=out:csv"
        )
    else:
        req.url = (
            f"https://docs.google.com/spreadsheets/d/{doc_id}/gviz/tq"
            f"?tq=select+A+,+G+where+A+contains+'{ability_name}'"
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


@inject
async def write_claim(
    guild_id: int,
    author_id: int,
    sheet_title: str,
    claims_dir: str = Provide[AppConfigContainer.config.db.claims_dir],
) -> None:
    guild_dir_path = os.path.join(claims_dir, str(guild_id))
    # TODO use the below as soon as aiofiles v0.8.0 gets released
    # await aiofiles.os.makedirs(guild_dir_path, exist_ok=True)
    # For now use the following workaround to create the dirs
    try:
        await aiofiles.os.mkdir(claims_dir)  # type: ignore[attr-defined]
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


@inject
async def read_claim(
    guild_id: int,
    author_id: int,
    claims_dir: str = Provide[AppConfigContainer.config.db.claims_dir],
) -> Optional[str]:
    author_file_path = os.path.join(claims_dir, str(guild_id), str(author_id))
    try:
        async with aiofiles.open(author_file_path, "r") as f:
            sheet_title = await f.read()
        return sheet_title
    except FileNotFoundError:
        return None


async def get_sheets_properties(
    aiog: Aiogoogle, sheets_service: Any, doc_id: str
) -> List[Dict[str, Any]]:
    req = sheets_service.spreadsheets.get(
        spreadsheetId=doc_id, fields=["sheets.properties"]
    )
    res = await aiog.as_service_account(
        req,
    )
    return [sheet["properties"] for sheet in res["sheets"]]


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


@bot.command(name="migrate", help="Migrate sheet from old format to new")
@inject
async def migrate(
    ctx: commands.Context,
    *args: str,
    character_sheet_hash: str = Provide[
        AppConfigContainer.config.gapi.character_sheet_hash
    ],
    aiog: Aiogoogle = Provide[AppConfigContainer.aiog],
) -> Any:
    if len(args) != 1:
        return await ctx.send(
            "ERROR: Invalid number of arguments."
            "Please provide the sheet you want to migrate as argument"
        )
    curr_sheet_title = args[0]
    new_sheet_title = f"{curr_sheet_title}_new"
    old_sheet_title = f"{curr_sheet_title}_old"

    async with aiog:
        sheets_service = await aiog.discover("sheets", "v4")
        sheet_props = await get_sheets_properties(
            aiog, sheets_service, character_sheet_hash
        )
        sheet_titles = [prop["title"] for prop in sheet_props]
        old_sheet_title_exists = old_sheet_title in sheet_titles
        curr_sheet_title_exists = curr_sheet_title in sheet_titles
        new_sheet_title_exists = new_sheet_title in sheet_titles
        if not curr_sheet_title_exists and not old_sheet_title_exists:
            return await ctx.send(
                f"ERROR: Cannot migrate {new_sheet_title}:"
                f"Either sheet {curr_sheet_title} or {old_sheet_title} must exist"
            )
        if old_sheet_title_exists and curr_sheet_title_exists:
            return await ctx.send(
                f"ERROR: Cannot migrate {new_sheet_title}: Already migrated"
            )

        # Get source values from the source
        source_sheet_title = (
            old_sheet_title if old_sheet_title_exists else curr_sheet_title
        )
        req = sheets_service.spreadsheets.values.batchGet(
            spreadsheetId=character_sheet_hash,
            ranges=[
                f"{source_sheet_title}!A2:A6",
                f"{source_sheet_title}!C2:C6",
                f"{source_sheet_title}!A8:A26",
                f"{source_sheet_title}!C8:C26",
                f"{source_sheet_title}!A28:A39",
                f"{source_sheet_title}!C28:C39",
                f"{source_sheet_title}!A42:A44",
                f"{source_sheet_title}!C42:C44",
                f"{source_sheet_title}!A47:A55",
                f"{source_sheet_title}!C47:C55",
            ],
        )
        res = await aiog.as_service_account(
            req,
        )
        res = res["valueRanges"]
        ability_to_xp: Dict[str, int] = {}
        for i in range(0, len(res), 2):
            keys = res[i]["values"]
            vals = res[i + 1]["values"]
            # Google Sheets API cuts off empty cells. in the end of a range
            # Fill them up again in the vals so that the zip below works
            if len(vals) < len(keys):
                vals += [[]] * (len(keys) - len(vals))
            for _key, _val in zip(keys, vals):
                key = _key[0]
                if key:
                    val = int(_val[0]) if len(_val) else 0
                    ability_to_xp[key] = val

        # Create the new sheet by duplicating Blanko
        blanko_sheet_id = sheet_props[sheet_titles.index("Blanko")]["sheetId"]
        source_sheet_index = sheet_props[sheet_titles.index(source_sheet_title)][
            "index"
        ]
        updateRequests = []
        # If there is already a sheet with the new title, delete it first
        if new_sheet_title_exists:
            new_sheet_id = sheet_props[sheet_titles.index(new_sheet_title)]["sheetId"]
            updateRequests.append({"deleteSheet": {"sheetId": new_sheet_id}})
        # Insert duplicated sheet
        updateRequests.append(
            {
                "duplicateSheet": {
                    "sourceSheetId": blanko_sheet_id,
                    "insertSheetIndex": source_sheet_index + 1,
                    "newSheetName": new_sheet_title,
                }
            }
        )

        req = sheets_service.spreadsheets.batchUpdate(
            spreadsheetId=character_sheet_hash,
            data=json.dumps({"requests": updateRequests}),
        )
        res = await aiog.as_service_account(
            req,
        )

        # Get all the values on the new sheet
        req = sheets_service.spreadsheets.values.batchGet(
            spreadsheetId=character_sheet_hash,
            ranges=[f"{new_sheet_title}!A:A", f"{new_sheet_title}!D:D"],
        )
        res = await aiog.as_service_account(
            req,
        )
        keys = res["valueRanges"][0]["values"]
        update_ranges: List[Dict[str, Any]] = []
        range_values: List[int] = []
        for range_end, _key in enumerate(keys, start=0):
            value: Optional[int] = ability_to_xp.get(_key[0]) if len(_key) else None
            if value is None:
                if len(range_values):
                    range_begin = range_end - len(range_values) + 1
                    update_ranges.append(
                        {
                            "range": f"{new_sheet_title}!D{range_begin}:D{range_end}",
                            "values": [
                                [] if val is None else [val] for val in range_values
                            ],
                        }
                    )
                    range_values = []
            else:
                range_values.append(value)

        req = sheets_service.spreadsheets.values.batchUpdate(
            spreadsheetId=character_sheet_hash,
            data=json.dumps(
                {"data": update_ranges, "valueInputOption": "USER_ENTERED"}
            ),
        )
        res = await aiog.as_service_account(
            req,
        )

        # If we got here, we can rename the current sheet (if any) to old and the new to current
        sheet_props = await get_sheets_properties(
            aiog, sheets_service, character_sheet_hash
        )
        sheet_titles = [prop["title"] for prop in sheet_props]
        new_sheet_id = sheet_props[sheet_titles.index(new_sheet_title)]["sheetId"]

        # rename current to old if old does not exist. Otherwise delete current
        updateRequests = []
        if curr_sheet_title_exists and not old_sheet_title_exists:
            curr_sheet_id = sheet_props[sheet_titles.index(curr_sheet_title)]["sheetId"]
            updateRequests.append(
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": curr_sheet_id,
                            "title": old_sheet_title,
                        },
                        "fields": "title",
                    }
                }
            )
        elif curr_sheet_title_exists:
            curr_sheet_id = sheet_props[sheet_titles.index(curr_sheet_title)]["sheetId"]
            updateRequests.append({"deleteSheet": {"sheetId": curr_sheet_id}})
        # rename new sheet to current sheet
        updateRequests.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": new_sheet_id, "title": curr_sheet_title},
                    "fields": "title",
                }
            }
        )

        req = sheets_service.spreadsheets.batchUpdate(
            spreadsheetId=character_sheet_hash,
            data=json.dumps({"requests": updateRequests}),
        )
        res = await aiog.as_service_account(
            req,
        )

        return await ctx.send(
            f"Successfully migrated sheet {curr_sheet_title}."
            f"The old sheet can be found in {old_sheet_title}"
        )


@bot.command(name="claim", help="Bind a character sheet to your user")
@inject
async def claim(
    ctx: commands.Context,
    *args: str,
    character_sheet_hash: str = Provide[
        AppConfigContainer.config.gapi.character_sheet_hash
    ],
    aiog: Aiogoogle = Provide[AppConfigContainer.aiog],
) -> Any:
    if len(args) != 1:
        return await ctx.send(
            "ERROR: Invalid number of arguments."
            " Please provide exactly one character sheet name!"
            ' If the name contains whitespaces, surround it with "",'
            ' i.e. "(sheet name with whitespaces)"'
        )
    sheet_title = args[0]

    async with aiog:
        sheets_service = await aiog.discover("sheets", "v4")
        sheet_props = await get_sheets_properties(
            aiog, sheets_service, character_sheet_hash
        )
        sheet_titles = [prop["title"] for prop in sheet_props]

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


def parse_int(string: str) -> Optional[int]:
    try:
        res = int(string)
        return res
    except ValueError:
        return None


@bot.command(name="roll", help="Roll any dice expression")
async def roll(ctx: commands.Context, *args: str) -> Any:
    guild_id = ctx.message.guild.id
    author_id = ctx.message.author.id
    character_name = await read_claim(guild_id, author_id)
    roller_name = ctx.message.author if character_name is None else character_name

    expression: str = ""
    result: int = 0
    sign: int = 1
    for idx, arg in enumerate(args):
        if idx % 2 == 0:
            # Try to extract dice or constant
            expr = arg.split("d")
            valid = True
            if len(expr) == 2:
                num_expr: str = expr[0]
                num: Optional[int] = parse_int(num_expr) if len(num_expr) else 1

                sides_expr: str = expr[1]
                sides: Optional[int] = parse_int(sides_expr)
                if num is None or num < 0 or sides is None or sides < 0:
                    valid = False
                else:
                    rolls = np.random.randint(1, sides, size=num)
                    result += sign * np.sum(rolls)
                    rolls_expr = ",".join(str(r) for r in rolls)
                    expression += f"{num}d{sides}({rolls_expr})"

            elif len(expr) == 1:
                constant: Optional[int] = parse_int(expr[0])
                if constant is None or constant < 0:
                    valid = False
                else:
                    result += sign * constant
                    expression += f"{constant}"
            else:
                valid = False
            if not valid:
                return await ctx.send(
                    f"@{ctx.message.author}: {arg} is not a valid dice roll expression"
                )
        else:
            if arg == "+":
                sign = 1
                expression += " + "
            elif arg == "-":
                sign = -1
                expression += " - "
            else:
                return await ctx.send(
                    f"@{ctx.message.author}: {arg} is not a valid seperator in dice roll expression"
                )
            if idx == len(args) - 1:
                return await ctx.send(
                    f"@{ctx.message.author}: dice roll expression cannot end with seperator {arg}"
                )
    if len(expression) == 0:
        return await ctx.send(
            f"@{ctx.message.author} nothing to roll in dice roll expression!"
        )
    return await ctx.send(f"{roller_name} rolls {expression}: **{result}**")


@inject
async def check_impl(
    ctx: commands.Context,
    character_name: str,
    *args: str,
    character_sheet_hash: str = Provide[
        AppConfigContainer.config.gapi.character_sheet_hash
    ],
    aiog: Aiogoogle = Provide[AppConfigContainer.aiog],
) -> Any:
    expression: List[Union[Tuple[str, int], str]] = []
    async with aiog:
        sheets_service = await aiog.discover("sheets", "v4")
        # First make sure that the character_name belongs to a valid sheet
        sheet_props = await get_sheets_properties(
            aiog, sheets_service, character_sheet_hash
        )
        sheet_titles = [prop["title"] for prop in sheet_props]
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
                    character_sheet_hash,
                    character_name,
                    name,
                    lowercast=False,
                )
                if len(name_value_pairs) == 0:
                    # No results found, try again with lowercasting
                    name_value_pairs = await get_ability_by_name(
                        aiog,
                        sheets_service,
                        character_sheet_hash,
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
    plus = np.random.randint(1, 5)
    minus = np.random.randint(1, 5)

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


@inject
def main(
    discord_bot_token: str = Provide[
        AppConfigContainer.config.discord.discord_bot_token
    ],
) -> None:
    bot.run(discord_bot_token)


async def init_resources(container: AppConfigContainer) -> Awaitable[None]:
    awaitable = container.init_resources()
    assert awaitable is not None
    return awaitable


if __name__ == "__main__":
    config_container = AppConfigContainer()
    config_container.wire(modules=[__name__])
    asyncio.run(init_resources(config_container))
    main()
