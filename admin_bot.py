import csv
import io
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import ADMIN_BOT_TOKEN, ADMIN_IDS
from database import get_chat_history
from ai_assistant import ask_yandex_gpt

bot = Bot(token=ADMIN_BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    # Проверка прав администратора
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен.")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("ℹ️ Использование: `/export <chat_id> <days>`\nПример: `/export -1001234567 7`")
        return

    try:
        chat_id = int(args[1])
        days = int(args[2])
    except ValueError:
        await message.answer("❌ Некорректные параметры команды.")
        return

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    await message.answer("🔄 Извлекаю данные из PostgreSQL и формирую файл...")
    history = await get_chat_history(chat_id, start_date, end_date)

    if not history:
        await message.answer("По переписке за этот период записей не обнаружено.")
        return

    # Создание CSV в оперативной памяти (без мусора на диске)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата (UTC)", "User ID", "Username", "Текст", "Медиа", "Реакции"])

    for msg in history:
        writer.writerow([msg.created_at, msg.user_id, msg.username, msg.text, msg.media_type, msg.reactions])

    output.seek(0)
    file_bytes = bytes(output.read(), "utf-8")
    document = types.BufferedInputFile(file_bytes, filename=f"export_{chat_id}.csv")

    await bot.send_document(chat_id=message.chat.id, document=document)

@dp.message(Command("ask"))
async def cmd_ask(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    # Использование: /ask <chat_id> <вопрос>
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("ℹ️ Использование: `/ask <chat_id> <вопрос>`\nПример: `/ask -1001234567 Что решили по дизайну?`")
        return

    try:
        chat_id = int(parts[1])
        user_query = parts[2]
    except ValueError:
        await message.answer("❌ Некорректный ID чата.")
        return

    await message.answer("🔍 Сканирую базу PostgreSQL и анализирую через YandexGPT...")

    # Достаем логи за неделю для анализа
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    history = await get_chat_history(chat_id, start_date, end_date)

    if not history:
        await message.answer("История сообщений за неделю пуста.")
        return

    # Формируем компактный текстовый блок для нейросети
    context_lines = []
    for msg in history:
        if msg.text:
            author = msg.username if msg.username else f"ID_{msg.user_id}"
            context_lines.append(f"[{msg.created_at.strftime('%d.%m %H:%M')}] {author}: {msg.text}")

    context = "\n".join(context_lines)
    
    # Лимит контекста для базовой модели YandexGPT Lite (~40k символов)
    if len(context) > 40000:
        context = context[-40000:]

    ai_response = await ask_yandex_gpt(context, user_query)
    await message.answer(f"🤖 **Ответ YandexGPT:**\n\n{ai_response}")

async def start_admin_bot():
    print("Запуск бота администратора...")
    await dp.start_polling(bot)
