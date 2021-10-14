# bot.py
import os
from numpy import random

from aiogoogle import Aiogoogle
from aiogoogle.models import HTTPError as AiogoogleHttpError
from aiogoogle.auth.creds import ServiceAccountCreds

import discord
from discord.ext import commands

from dotenv import load_dotenv
import  io
import csv

bot = commands.Bot(command_prefix='!')
CHARACTER_SHEET_HASH = None

class SheetNotFoundError(Exception):
    def __init__(self, sheet_title):
        super().__init__(f"Sheet with title '{sheet_title}' not found!")

@bot.event
async def on_ready():
    print(f'Bot has connected to Discord!')

@bot.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise


@bot.command(name='hello', help="Say hello")
async def hello(ctx):
    response = f"You said '{ctx.message.content}'"
    await ctx.send(response)

async def get_ability_by_name(aiog: Aiogoogle, sheets_service, doc_id, sheet_title, ability_name):
    req = sheets_service.spreadsheets.values.get(spreadsheetId=doc_id, range=sheet_title)
    req.url = f"https://docs.google.com/spreadsheets/d/{CHARACTER_SHEET_HASH}/gviz/tq?tq=select+A+,+F+where+lower(A)+contains+'{ability_name.lower()}'+limit+3&sheet={sheet_title}&tqx=out:csv"
    try:
        res_csv = await aiog.as_service_account(
            req,
        )
        # extract all names and values from the csv response
        name_value_pairs = []
        for line in res_csv.split('\n'):
            if len(line) == 0:
                continue
            name, value = line.replace('"','').split(',') # remove all "" and split at ,
            value = int(value)
            name_value_pairs.append((name,value))
        return name_value_pairs
    except AiogoogleHttpError as e:
        if e.res.status_code == 400:
            raise SheetNotFoundError(sheet_title)
        else:
            raise e

@bot.command(name='check', help = "Roll a value on the character sheet")
async def check(ctx, *args):
    # Setup aiogoogle with sheets READ credentials
    aiog = await setup_aiogoogle()

    expression = []
    async with aiog:
        sheets_service = await aiog.discover('sheets', 'v4')
        for idx, arg in enumerate(args):
            if idx % 2 == 0:
                # Try to extract ability name and value
                name = arg
                name_value_pairs = await get_ability_by_name(aiog, sheets_service, CHARACTER_SHEET_HASH, 'Genna', name) # TODO more generic
                if len(name_value_pairs) == 0:
                    return await ctx.send(f"ERROR: No ability matches '{name}'")
                if len(name_value_pairs) > 1:
                    return await ctx.send(f"ERROR: Multiple abilities ({[it[0] for it in name_value_pairs]} ...) match '{name}'. Please be more specific!")
                name, value = name_value_pairs[0]
                value = int(value)
                expression.append((name, value))
            else:
                # Try to extract seperator
                sep = arg
                if sep ==  "+" or sep == "-":
                    expression.append(sep)
                else:
                    response = f"ERROR: {sep} is an invalid seperator. Valid seperators are '+' or '-'"
                    return await ctx.send(response)

                if idx == len(args)-1:
                    response = "ERROR: expression {} ends with a seperator!".format(ctx.message.content)
                    return await ctx.send(response)

    if len(expression) == 0:
        return await ctx.send("Nothing to roll!")

    # Happy path
    plus = random.randint(1, 5)
    minus = random.randint(1, 5)

    if len(expression) == 1:
        name, value = expression[0]
        response = "Rolling 2 x {} + d4 - d4 = {} + {} - {} = **{}**".format(name, 2*value, plus, minus, 2*value + plus - minus)
    else:
        response_first = ""
        response_second = ""
        result = plus - minus
        prev_sep = "+"
        for idx, name_value_or_sep in enumerate(expression):
            if idx % 2 == 0:
                # name, value pair
                (name, value) = name_value_or_sep
                response_first += name
                response_second += "{}".format(value)
                if prev_sep == "+":
                    result += value
                else:
                    result -= value
            else:
                # seperator
                sep = name_value_or_sep
                response_first += " {} ".format(sep)
                response_second += " {} ".format(sep)
                prev_sep = sep

        response = "Rolling {} + d4 - d4 = {} + {} - {} = **{}**".format(response_first, response_second, plus, minus, result)
    await ctx.send(response)


def getenv_required(env):
    if env in os.environ:
        return os.environ[env]
    raise ValueError(f"Environment variable '{env}' needs to be set!")

async def setup_aiogoogle():
    creds = ServiceAccountCreds(
      scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    aiog = Aiogoogle(service_account_creds=creds)
    # Notice this line. Here, Aiogoogle loads the service account key.
    await aiog.service_account_manager.detect_default_creds_source()
    return aiog



if __name__ == "__main__":
  # Load env parameters
  load_dotenv()

  DISCORD_BOT_TOKEN = getenv_required('DISCORD_BOT_TOKEN')
  CHARACTER_SHEET_HASH = getenv_required('CHARACTER_SHEET_HASH')
  _ = getenv_required('GOOGLE_APPLICATION_CREDENTIALS') # just make sure it is set

  bot.run(DISCORD_BOT_TOKEN)

