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
        ctx = args[0] if args else None
        try:
            return await func(*args, **kwargs)

        except ClientError as e:
            if e.code == 429:
                await ctx.reply('Лимит модели пока исчерпан. '
                                'Подождите, пока токены восстановятся.')
            elif e.code == 400 and 'FAILED_PRECONDITION' in str(e):
                await ctx.reply('Ошибка настройки прокси на сервере Gemini. '
                                'Напишите админу в tg: @kseruk')
            elif e.code == 400:
                await ctx.reply('Этот запрос слишком длинный или некорректный. Переформулируйте его.')
            else:
                await ctx.reply(f'Ошибка клиента Gemini (Код {e.code}). '
                                f'Отправьте в тг админу @kseruk это: {e}')

        except ServerError as e:
            if e.code == 503:
                await ctx.reply('Серверы Gemini сейчас перегружены. '
                                'Попробуйте снова через пару минут.')
            else:
                await ctx.reply(f'Серверная ошибка Gemini (Код {e.code}). '
                                f'Попробуйте позже или напишите админу @kseruk: {e}')

        except APIError as e:
            await ctx.reply(f'Сбой API Gemini. Отправьте админу @kseruk: {e}')

        except Exception as e:
            await ctx.reply(f'Неизвестная ошибка бота. Отправьте в тг админу @kseruk это: {e}')

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

@discordBot.command()
@try_decorator
async def ai(ctx, *content):
    if ctx.message.reference:
        original = await ctx.fetch_message(ctx.message.reference.message_id)
        response = await generate_async('Прошлое сообщение диалога: '+
                                        f'{original.author.name}: {original.content}' +
                                        '\nВопрос пользователя: ' + ' '.join(content))
        await ctx.reply(response.text)
    else:
        response = await generate_async(' '.join(content))
        await ctx.reply(response.text)

@discordBot.command()
@try_decorator
async def aihelp(ctx):
    await ctx.reply('Команды бота: \n\n' + config.botCommands)

@discordBot.command()
@try_decorator
async def retell(ctx, n: int = 50):
    n = abs(n)
    messages = []
    async for message in ctx.channel.history(limit=n):
        messages.append(message.author.name + ': ' + message.content + '\n')
    response = await generate_async('Сейчас ты увидишь диалог чата. '
                        'Твоя задача кратко пересказать, '
                        'о чём был диалог, '
                        'чтобы не пришлось читать '
                        'все эти сообщения.\n'
                        + ''.join(messages[1:][::-1]))
    await ctx.reply(response.text)

@discordBot.command()
@try_decorator
async def context_ai(ctx, *content):
    messages = []
    async for message in ctx.channel.history(limit=100):
        messages.append(message.created_at.strftime("%d.%m.%Y %H:%M") + ' ' +
                        message.author.name + ': ' + message.content + '\n')
    response = await generate_async('Ответь на вопрос максимально кратко:' + ' '.join(content) + '\n'
                                     + 'Используй для точного ответа и поиска нужной информации'
                                     ' диалог пользователей:'
                        + ''.join(messages[1:][::-1]))
    await ctx.reply(response.text)

@discordBot.command()
@try_decorator
async def explain(ctx):
    if ctx.message.reference:
        original = await ctx.fetch_message(ctx.message.reference.message_id)
        response = await generate_async('Сейчас ты увидишь сложный запрос. '
                            'Если это код, определи его язык, добавь пояснения '
                            'и объясни функционал. Если это сложные уравнения,'
                            ' термины и т.д., то объясни всё современным языком, '
                            'чтобы было максимально понятно. Можешь использовать шутки '
                            'и мемы.'
                            'Вот запрос: \n'
                            + original.content)
        await ctx.reply(response.text)
    else:
        await ctx.reply('Нужно ответить на чьё-то сообщение, чтобы я знал, что я должен объяснить!')


discordBot.run(config.discordToken)