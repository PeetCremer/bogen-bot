# bot.py
import os
from numpy import random

import discord
from discord.ext import commands

from dotenv import load_dotenv

from character_sheet import CharacterSheet

import  io
import csv



bot = commands.Bot(command_prefix='!')

sheet = None

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

@bot.command(name='update_sheet', help="Update the character sheet")
async def update_sheet(ctx):
    new_sheet = sheet.update_sheet()
    response = "OK"
    await ctx.send(response)

@bot.command(name='print_sheet', help = "Print the currently loaded character sheet")
async def print_sheet(ctx):
    response = str(sheet.sheet)
    await ctx.send(response)


@bot.command(name='check', help = "Roll a value on the character sheet")
async def check(ctx, *args):
    # validate args
    expression = []
    for idx, arg in enumerate(args):
        if idx % 2 == 0:
            # Try to extract value
            val = sheet.sheet.get(arg, None)
            if val is None:
                response = "ERROR: Key {} not found in character sheet".format(arg)
                return await ctx.send(response)
            expression.append((arg, val))
        else:
            # Try to extract seperator
            if arg ==  "+" or arg == "-":
                expression.append(arg)
            else:
                response = "ERROR: {} is an invalid seperator. Valid seperators are '+' or '-'".format(arg)
                return await ctx.send(response)

            if idx == len(args)-1:
                response = "ERROR: expression {} ends with a seperator!".format(ctx.message.content)
                return await ctx.send(response)

    if len(expression) == 0:
        response = "Nothing to roll!"
        return await ctx.send(response)

    # Happy path
    plus = random.randint(1, 5)
    minus = random.randint(1, 5)
    response = "2 x {} + d4 - d4 = {} + {} - {} = {} ".format(arg, 2*val, plus, minus, 2*val + plus - minus)

    if len(expression) == 1:
        arg, val = expression[0]
        response = "Rolling 2 x {} + d4 - d4 = {} + {} - {} = **{}**".format(arg, 2*val, plus, minus, 2*val + plus - minus)
    else:
        response_first = ""
        response_second = ""
        result = plus - minus
        prev_seperator = "+"
        for idx, arg_val_or_seperator in enumerate(expression):
            if idx % 2 == 0:
                #arg_val
                (arg, val) = arg_val_or_seperator
                response_first += arg
                response_second += "{}".format(val)
                if prev_seperator == "+":
                    result += val
                else:
                    result -= val
            else:
                # seperator
                seperator = arg_val_or_seperator
                response_first += " {} ".format(seperator)
                response_second += " {} ".format(seperator)
                prev_seperator = seperator

        response = "Rolling {} + d4 - d4 = {} + {} - {} = **{}**".format(response_first, response_second, plus, minus, result)

                
    await ctx.send(response)

            



if __name__ == "__main__":
  # Load env parameters
  load_dotenv()
  DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', None)
  if DISCORD_BOT_TOKEN is None:
    raise ValueError("Environnment variable 'DISCORD_BOT_TOKEN' has to be set!")
  CHARACTER_SHEET_URL = os.getenv('CHARACTER_SHEET_URL', None)
  if CHARACTER_SHEET_URL is None:
    raise ValueError("Environnment variable 'CHARACTER_SHEET_URL' has to be set!")
  
  # Initialize sheet
  sheet = CharacterSheet(CHARACTER_SHEET_URL)
  sheet.update_sheet()

  bot.run(DISCORD_BOT_TOKEN)

