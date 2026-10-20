import os
import csv
import io
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import Command
from config import ADMIN_BOT_TOKEN, ADMIN_IDS
from database import get_chat_history, save_message
from ai_assistant import ask_yandex_gpt

# Создаем папку для медиафайлов, если её нет
os.makedirs("downloads", exist_ok=True)

# Настройка стабильного альтернативного сервера Telegram API для обхода блокировок в РФ
local_server = TelegramAPIServer.from_base("https://telegram-proxy.org")
bot = Bot(token=ADMIN_BOT_TOKEN, server=local_server)
dp = Dispatcher()

# === МОДУЛЬ ИНТЕРФЕЙСА АДМИНИСТРАТОРА ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я корпоративный бот-аналитик. Система сбора и анализа запущена.")


# ПУНКТ 5: Экспорт по периоду дат с полной валидацией и ограничениями
@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещен.")
        return

    args = message.text.split()
    # Запрашиваем формат: /export <chat_id> <ДД.ММ.ГГГГ> <ДД.ММ.ГГГГ>
    if len(args) < 4:
        await message.answer(
            "ℹ️ Использование: `/export <chat_id> <дата_начала> <дата_конца>`\n"
            "Пример: `/export -1001234567 01.10.2026 15.10.2026`"
        )
        return

    try:
        chat_id = int(args[1])
        start_date = datetime.strptime(args[2], "%d.%m.%Y")
        # Устанавливаем конец дня для даты окончания (23:59:59)
        end_date = datetime.strptime(args[3], "%d.%m.%Y").replace(hour=23, minute=59, second=59)
    except ValueError:
        await message.answer("❌ Некорректный формат параметров. Используйте формат дат: ДД.ММ.ГГГГ")
        return

    # Защитные ограничения (Валидация)
    current_time = datetime.now()
    if start_date > end_date:
        await message.answer("❌ Ошибка: Дата начала не может быть позже даты окончания периода!")
        return
    if start_date > current_time or end_date > current_time:
        await message.answer("❌ Ошибка: Нельзя запрашивать данные из будущего времени!")
        return
    if end_date - start_date > timedelta(days=366):
        await message.answer("❌ Ошибка: Максимальный период выгрузки составляет 1 год!")
        return

    await message.answer(f"🔄 Извлекаю данные из PostgreSQL за период с {args[2]} по {args[3]}...")
    history = await get_chat_history(chat_id, start_date, end_date)

    if not history:
        await message.answer("По переписке за выбранный период записей в базе данных не обнаружено.")
        return

    # Формирование CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Дата (UTC)", "User ID", "Username", "Текст", "Тип медиа", "Путь к медиа", "Реакции"])

    for msg in history:
        writer.writerow([msg.created_at, msg.user_id, msg.username, msg.text, msg.media_type, msg.media_path, msg.reactions])

    output.seek(0)
    file_bytes = bytes(output.read(), "utf-8")
    document = types.BufferedInputFile(file_bytes, filename=f"export_{chat_id}_{args[2]}_{args[3]}.csv")

    await bot.send_document(chat_id=message.chat.id, document=document)


@dp.message(Command("ask"))
async def cmd_ask(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("ℹ️ Использование: `/ask <chat_id> <вопрос>`\nПример: `/ask -1001234567 Что решили?`")
        return
    try:
        chat_id = int(parts[1])
        user_query = parts[2]
    except ValueError:
        await message.answer("❌ Некорректный ID чата.")
        return

    await message.answer("🔍 Сканирую базу PostgreSQL и анализирую через YandexGPT...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    history = await get_chat_history(chat_id, start_date, end_date)

    if not history:
        await message.answer("История сообщений за неделю пуста.")
        return

    context_lines = []
    for msg in history:
        if msg.text:
            author = msg.username if msg.username else f"ID_{msg.user_id}"
            context_lines.append(f"[{msg.created_at.strftime('%d.%m %H:%M')}] {author}: {msg.text}")

    context = "\n".join(context_lines)
    if len(context) > 40000:
        context = context[-40000:]

    ai_response = await ask_yandex_gpt(context, user_query)
    await message.answer(f"🤖 **Ответ YandexGPT:**\n\n{ai_response}")


# === МОДУЛЬ АВТОМАТИЧЕСКОГО СБОРА ПЕРЕПИСОК (Пункт 1, 3, 4, 8) ===

@dp.message()
async def handle_new_message(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        try:
            text = message.text if message.text else message.caption
            media_type = None
            media_path = None

            # ПУНКТ 3: Физическое сохранение файлов, изображений и голосовых на диск
            if message.photo:
                media_type = "photo"
                file_id = message.photo[-1].file_id
                file_info = await message.bot.get_file(file_id)
                media_path = f"downloads/photo_{message.message_id}.jpg"
                await message.bot.download_file(file_info.file_path, media_path)
            elif message.document:
                media_type = "document"
                file_id = message.document.file_id
                file_info = await message.bot.get_file(file_id)
                media_path = f"downloads/doc_{message.message_id}_{message.document.file_name}"
                await message.bot.download_file(file_info.file_path, media_path)
            elif message.voice:
                media_type = "voice"
                file_id = message.voice.file_id
                file_info = await message.bot.get_file(file_id)
                media_path = f"downloads/voice_{message.message_id}.ogg"
                await message.bot.download_file(file_info.file_path, media_path)
            elif message.video:
                media_type = "video"

            # ПУНКТ 4: Извлекаем информацию о реакциях при наличии
            reactions_list = []
            if message.reactions and hasattr(message.reactions, 'reactions'):
                for reaction in message.reactions.reactions:
                    if hasattr(reaction, 'custom_emoji_id') and reaction.custom_emoji_id:
                        reactions_list.append(f"emoji_id:{reaction.custom_emoji_id}")
                    elif hasattr(reaction, 'emoji') and reaction.emoji:
                        reactions_list.append(reaction.emoji)
            reactions_str = ",".join(reactions_list) if reactions_list else None

            # Сохранение в PostgreSQL. 
            # ПУНКТ 8: Передаем точное время отправки сообщения из Telegram (message.date)
            await save_message(
                chat_id=message.chat.id,
                chat_title=message.chat.title,
                message_id=message.message_id,
                user_id=message.from_user.id if message.from_user else None,
                username=message.from_user.username if message.from_user else None,
                text=text,
                media_type=media_type,
                media_path=media_path,
                reactions=reactions_str,
                created_at=message.date.replace(tzinfo=None) # Очищаем временную зону для базы данных
            )
            print(f"📥 [{message.date.strftime('%X')}] Сообщение/Медиа из чата '{message.chat.title}' записано в PostgreSQL!")
        except Exception as e:
            print(f"Ошибка при обработке и сохранении сообщения: {e}")

async def start_admin_bot():
    print("Запуск единого модуля управления и сбора переписок через Bot API...")
    await dp.start_polling(bot)
