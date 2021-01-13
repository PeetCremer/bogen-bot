# bot.py
import os
from numpy import random

import discord
from discord.ext import commands

from dotenv import load_dotenv

import  io
import csv



load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', None)
if DISCORD_BOT_TOKEN is None:
  raise ValueError("Environnment variable 'DISCORD_BOT_TOKEN' has to be set!")



bot = commands.Bot(command_prefix='!')

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

@bot.command(name='upload_character', help="Uploads a character sheet in CSV format")
async def hello(ctx):
    # Try to extract a single csv file attachment
    attachments = ctx.message.attachments
    if len(attachments) != 1:
      response = f"ERROR: @{ctx.message.author} you need to attach a **single** character sheet in CSV format"
      return await ctx.send(response)
    attachment = attachments[0]

    result = {}
    csv_bytes = await attachment.read()
    csv_io = io.StringIO(csv_bytes.decode())
    reader = csv.reader(csv_io)
    try: 
      for row in reader:
        key, val = row
        result[key] = val
    except Exception as err:
      response = f"ERROR while trying to read attachment as CSV File. @{ctx.message.author} go and fix it!"
      return await ctx.send(response)

    # Happy path
    response = str(result)
    await ctx.send(response)


bot.run(DISCORD_BOT_TOKEN)