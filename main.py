import typing

from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands
from google import genai
import asyncio

import config
import os
from google.genai import types
from google.genai.errors import ClientError, ServerError, APIError
import functools

intents = discord.Intents().all()
genaiClient = genai.Client(api_key=config.geminiToken, http_options=types.HttpOptions(
        client_args={'proxy': config.proxyServer}))
discordBot = commands.Bot(command_prefix=config.prefix, intents=intents, proxy=config.proxyServer)
os.environ["HTTP_PROXY"] = config.proxyServer
os.environ["HTTPS_PROXY"] = config.proxyServer

def try_decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        interaction = args[0] if args else None
        try:
            try:
                return await func(*args, **kwargs)

            except ClientError as e:
                if e.code == 429:
                    await interaction.followup.send('Лимит модели пока исчерпан. '
                                    'Подождите, пока токены восстановятся.')
                elif e.code == 400 and 'FAILED_PRECONDITION' in str(e):
                    await interaction.followup.send('Ошибка настройки прокси на сервере Gemini. '
                                    'Напишите админу в tg: @kseruk')
                elif e.code == 400:
                    await interaction.followup.send('Этот запрос слишком длинный или некорректный. Переформулируйте его.')
                else:
                    await interaction.followup.send(f'Ошибка клиента Gemini (Код {e.code}). '
                                    f'Отправьте в тг админу @kseruk это: {e}')

            except ServerError as e:
                if e.code == 503:
                    await interaction.followup.send('Серверы Gemini сейчас перегружены. '
                                    'Попробуйте снова через пару минут.')
                else:
                    await interaction.followup.send(f'Серверная ошибка Gemini (Код {e.code}). '
                                    f'Попробуйте позже или напишите админу @kseruk: {e}')

            except APIError as e:
                await interaction.followup.send(f'Сбой API Gemini. Отправьте админу @kseruk: {e}')

            except Exception as e:
                    await interaction.followup.send(f'Неизвестная ошибка бота. Отправьте в тг админу @kseruk это: {e}')
        except discord.NotFound as e:
            await interaction.channel.send(
                f'{interaction.user.mention} Неизвестная ошибка бота. Отправьте в тг админу @kseruk это: {e}')

    return wrapper

def generate(prompt: str) -> str:
    GLOBAL_MEMORY = ('Отвечай без '
                     'специального форматирования, '
                     'только текст\n'
                     'Твоё сообщение не должно превышать лимит СТРОГО 1950'
                     'символов. Если это код, '
                     'просто поясни его, если он слишком длинный. По возможности '
                     'отправляй код или решения целиком, если они вмещаются в лимит '
                     '1950 символов (с пробелами). НИКАК НЕ КОММЕНТИРУЙ ТО, ЧТО НАПИСАНО ВЫШЕ.'
                     ' Вот запрос, который нужно обработать (отвечай на языке, который '
                     'будет использован далее в запросе):\n')
    response = genaiClient.models.generate_content(model=config.geminiModel,
                                                   contents=GLOBAL_MEMORY + prompt)
    return response

async def generate_async(prompt: str) -> str:
    async with asyncio.Semaphore(1):
        return await asyncio.to_thread(generate, prompt)

@discordBot.event
async def on_ready():
    print(f"Бот {discordBot.user.name} успешно запущен!")
    try:
        synced = await discordBot.tree.sync()
        print(f"Синхронизировано команд: {len(synced)}")
    except Exception as e:
        print(f"Ошибка синхронизации: {e}")

@discordBot.tree.command(name="ai", description="Генерация ответа ИИ")
@try_decorator
async def ai(interaction: discord.Interaction, content: str):
    await interaction.response.defer(ephemeral=False)
    prompt = content
    response = await generate_async(prompt)
    await interaction.followup.send(response.text)

@discordBot.tree.context_menu(name="Объяснить простым языком")
@try_decorator
async def explain(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=False)
    response = await generate_async('Сейчас ты увидишь сложный запрос. '
                                    'Если это код, определи его язык, добавь пояснения '
                                    'и объясни функционал. Если это сложные уравнения,'
                                    ' термины и т.д., то объясни всё современным языком, '
                                    'чтобы было максимально понятно. Можешь использовать шутки '
                                    'и мемы.'
                                    'Вот запрос: \n'
                                    + message.content)
    await interaction.followup.send(response.text)

@discordBot.tree.command(name="help", description="Помощь по боту")
@try_decorator
async def aihelp(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    await interaction.followup.send('Команды бота: \n\n' + config.botCommands)

@discordBot.tree.command(name="retell", description="Пересказ последних N сообщений чата")
@try_decorator
async def retell(interaction: discord.Interaction, n: discord.app_commands.Range[int, 1, 100] = 50):
    await interaction.response.defer(ephemeral=False)
    n = abs(n)
    messages = []
    async for message in interaction.channel.history(limit=n):
        if message.content:
            messages.append(message.author.name + ': ' + message.content + '\n')
    if not messages:
        await interaction.followup.send("В чате не найдено текстовых сообщений для анализа.")
        return
    response = await generate_async('Сейчас ты увидишь диалог чата. '
                                    'Твоя задача кратко пересказать, '
                                    'о чём был диалог, '
                                    'чтобы не пришлось читать '
                                    'все эти сообщения.\n'
                                    + ''.join(messages[1:][::-1]))
    await interaction.followup.send(response.text)

@discordBot.tree.command(name="context_ai", description="Поиск нужной информации в чате")
@try_decorator
async def context_ai(interaction: discord.Interaction, content: str):
    await interaction.response.defer(ephemeral=False)
    messages = []
    async for message in interaction.channel.history(limit=100):
        if message.content:
            messages.append(message.created_at.strftime("%d.%m.%Y %H:%M") + ' ' +
                        message.author.name + ': ' + message.content + '\n')
    response = await generate_async('Ответь на вопрос максимально кратко:' + ' '.join(content) + '\n'
                                     + 'Используй для точного ответа и поиска нужной информации'
                                     ' диалог пользователей:'
                        + ''.join(messages[1:][::-1]))
    await interaction.followup.send(response.text)

discordBot.run(config.discordToken)