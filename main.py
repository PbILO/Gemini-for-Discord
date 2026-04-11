import discord
from discord.ext import commands
from google import genai

from config import *

intents = discord.Intents().all()
genaiClient = genai.Client(api_key=geminiToken)
discordBot = commands.Bot(command_prefix=prefix, intents=intents)

@discordBot.command()
async def ai(message, content):
    response = genaiClient.models.generate_content(model="gemini-3-flash-preview", contents='ответь текстом (на языке запроса) без какого-либо специального форматирования, чтобы это можно было скопировать и отправить сообщением' + content)
    await message.reply(response.text)


discordBot.run(discordToken)