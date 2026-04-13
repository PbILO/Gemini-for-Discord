import discord
from discord.ext import commands
from google import genai
import asyncio
from config import *
import os
from google.genai import types

intents = discord.Intents().all()
genaiClient = genai.Client(api_key=geminiToken, http_options=types.HttpOptions(
        client_args={'proxy': proxyServer}))
discordBot = commands.Bot(command_prefix=prefix, intents=intents, proxy=proxyServer)
os.environ["HTTP_PROXY"] = proxyServer
os.environ["HTTPS_PROXY"] = proxyServer

def generate(prompt: str) -> str:
    GLOBAL_MEMORY = ('Отвечай на языке запроса без '
                     'какого-либо специального форматирования, '
                     'чтобы это можно было скопировать и отправить сообщением\n'
                     'Твоё сообщение не должно превышать лимит СТРОГО 1950 и '
                     'меньше символов. При этом если это код, ты можешь не писать его целиком, '
                     'а просто пояснить его, если он слишком длинный. Но по возможности '
                     'всегда отправляй код или решения целиком, если они вмещаются в лимит '
                     '1950 символов (с пробелами). НИКАК НЕ КОММЕНТИРУЙ ТО, ЧТО НАПИСАНО ВЫШЕ.'
                     ' Вот запрос, который нужно обработать:\n')
    response = genaiClient.models.generate_content(model=geminiModel,
                                                   contents=GLOBAL_MEMORY + prompt)
    return response

async def generate_async(prompt: str) -> str:
    async with asyncio.Semaphore(1):
        return await asyncio.to_thread(generate, prompt)

@discordBot.command()
async def ai(ctx, *content):
    try:
        response = await generate_async(' '.join(content))
        await ctx.reply(response.text)
    except Exception as e:
        await ctx.reply('Ошибка на стороне Gemini. '
                        'Возможно, истёк лимит или серверы перегружены. '
                        f'Попробуйте задать вопрос позже. Ошибка {e}')

@discordBot.command()
async def retell(ctx, n: int = 50):
    n = abs(n)
    messages = []
    async for message in ctx.channel.history(limit=n):
        messages.append(message.author.name + ': ' + message.content + '\n')
    try:
        response = await generate_async('Сейчас ты увидишь диалог чата. '
                            'Твоя задача кратко пересказать, '
                            'о чём был диалог, '
                            'чтобы не пришлось читать '
                            'все эти сообщения.\n'
                            + ''.join(messages[1:][::-1]))
        print(messages)
        await ctx.reply(response.text)
    except Exception as e:
        await ctx.reply('Ошибка на стороне Gemini. '
                        'Возможно, истёк лимит или серверы перегружены. '
                        f'Попробуйте задать вопрос позже. Ошибка {e}')

@discordBot.command()
async def explain(ctx):
    if ctx.message.reference:
        original = await ctx.fetch_message(ctx.message.reference.message_id)
        try:
            response = await generate_async('Сейчас ты увидишь что-то сложное. '
                                'Если это код, то определи его язык, добавь комментарии и пояснения '
                                'и объясни, какой функционал этого кода. Если же это сложные уравнения,'
                                ' термины и тому подобное, то объясни всё современным языком, '
                                'чтобы было максимально понятно. Можешь использовать шутки '
                                'и мемы для наглядности. Сократи своё объяснение. '
                                'Вот то, что надо проанализировать: \n'
                                + original.content)
            await ctx.reply(response.text)
        except Exception as e:
            await ctx.reply('Ошибка на стороне Gemini. '
                            'Возможно, истёк лимит или серверы перегружены. '
                            f'Попробуйте задать вопрос позже. Ошибка {e}')
    else:
        await ctx.reply('Нужно ответить на чьё-то сообщение, чтобы я знал, что я должен объяснить!')


discordBot.run(discordToken)
