import os
import asyncio
import functools
from vkbottle.bot import Bot, Message
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError, APIError
from config import *

os.environ["HTTP_PROXY"] = proxyServer
os.environ["HTTPS_PROXY"] = proxyServer

genaiClient = genai.Client(api_key=geminiToken, http_options=types.HttpOptions(
    client_args={'proxy': proxyServer}))

bot = Bot(token = vkToken)

def try_decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        message = args[0] if args else None
        try:
            return await func(*args, **kwargs)

        except ClientError as e:
            if e.code == 429:
                await message.answer('Лимит модели пока исчерпан. '
                                'Подождите, пока токены восстановятся.')
            elif e.code == 400 and 'FAILED_PRECONDITION' in str(e):
                await message.answer('Ошибка настройки прокси на сервере Gemini. '
                                'Напишите админу в tg: @kseruk')
            elif e.code == 400:
                await message.answer('Этот запрос слишком длинный или некорректный. Переформулируйте его.')
            else:
                await message.answer(f'Ошибка клиента Gemini (Код {e.code}). '
                                f'Отправьте в тг админу @kseruk это: {e}')

        except ServerError as e:
            if e.code == 503:
                await message.answer('Серверы Gemini сейчас перегружены. '
                                'Попробуйте снова через пару минут.')
            else:
                await message.answer(f'Серверная ошибка Gemini (Код {e.code}). '
                                f'Попробуйте позже или напишите админу @kseruk: {e}')

        except APIError as e:
            await message.answer(f'Сбой API Gemini. Отправьте админу @kseruk: {e}')

        except Exception as e:
            if "Access denied" in str(e):
                await message.answer(
                    "В настоящее время история чатов не доступна для бота (свойства vk), только в личных сообщениях.")
            else:
                await message.answer(f"Неизвестная ошибка бота. Отправьте в тг админу @kseruk это: {e}")

    return wrapper

def generate(prompt: str) -> str:
    GLOBAL_MEMORY = ('Отвечай без '
                     'специального форматирования, '
                     'только текст\n'
                     'Твоё сообщение не должно превышать лимит СТРОГО 4096'
                     'символов. Если это код, '
                     'просто поясни его, если он слишком длинный. По возможности '
                     'отправляй код или решения целиком, если они вмещаются в лимит '
                     '1950 символов (с пробелами). НИКАК НЕ КОММЕНТИРУЙ ТО, ЧТО НАПИСАНО ВЫШЕ.'
                     ' Вот запрос, который нужно обработать (отвечай на языке, который '
                     'будет использован далее в запросе):\n')
    response = genaiClient.models.generate_content(model=geminiModel,
                                                   contents=GLOBAL_MEMORY + prompt)
    return response

async def generate_async(prompt: str) -> str:
    async with asyncio.Semaphore(1):
        return await asyncio.to_thread(generate, prompt)

@bot.on.message(text = f"{prefix}ai <args>")
@try_decorator
async def ai(message: Message, args: str):
    if not args or not args.strip():
        await message.answer("Пожалуйста, введите текст запроса после команды.")
        return
    response = await generate_async(args)
    await message.answer(response.text)

@bot.on.message(text=f"{prefix}retell <args>")
@try_decorator
async def retell(message: Message, args: str):
    n = 50
    clean_args = args.strip()

    if clean_args:
        if clean_args.isdigit():
            n = abs(int(clean_args))
            if n > 200:
                n = 200
        else:
            await message.answer(
                "После команды /retell нужно указывать число (количество сообщений). Например: /retell 20"
            )
            return

    history = await bot.api.messages.get_history(peer_id=message.peer_id, count=n)
    messages = []
    for m in history.items:
        if m.text:
            messages.append(f"User_{m.from_id}: {m.text}\n")
    response = await generate_async(
        'Сейчас ты увидишь диалог чата. '
        'Твоя задача кратко пересказать, '
        'о чём был диалог, '
        'чтобы не пришлось читать '
        'все эти сообщения.\n'
        + ''.join(messages[1:][::-1]))
    await message.answer(response.text)

@bot.on.message(text=f"{prefix}explain")
@try_decorator
async def explain(message: Message):
    target_text = ""
    if message.reply_message and message.reply_message.text:
        target_text = message.reply_message.text
    else:
        await message.answer('Нужно ответить на чьё-то сообщение, чтобы я знал, что я должен объяснить!')
        return

    response = await generate_async(
        'Сейчас ты увидишь сложный запрос. Если это код, определи его язык, добавь пояснения '
        'и объясни функционал. Если это сложные уравнения, термины и т.д., то объясни всё '
        'современным языком, чтобы было максимально понятно. Можешь использовать шутки и мемы. '
        f'Вот запрос: \n {target_text}'
    )
    await message.answer(response.text)

bot.run_forever()