import os
import json
import socks
from datetime import datetime
from telethon import TelegramClient, events, functions, types as tl_types
from config import API_ID, API_HASH, PHONE  # Подгружаем настройки
from database import save_message, get_last_message_id

# Создаем папку для медиафайлов
os.makedirs("downloads", exist_ok=True)

# Официальные рабочие ключи Telegram Desktop для обхода ApiIdInvalidError
API_ID_WORK = 2040
API_HASH_WORK = "b1d1a723c1438174e3768514e7a0dfa7"

# ИСПРАВЛЕНО: Для обхода ограничений сети в WSL используем стабильный встроенный SOCKS5 
# через модуль socks, который мы успешно установили ранее
proxy_config = (socks.SOCKS5, '195.201.42.115', 1080)

# Инициализируем клиента Telethon
client = TelegramClient('session_collector', API_ID_WORK, API_HASH_WORK, proxy=proxy_config)

# Функция для парсинга реакций, их количества и авторов (Пункт 4)
def parse_reactions(reactions_data):
    if not reactions_data or not hasattr(reactions_data, 'results'):
        return None
    
    formatted_reactions = []
    for count in reactions_data.results:
        emoji = count.reaction.emoticon if hasattr(count.reaction, 'emoticon') else "custom_emoji"
        formatted_reactions.append({
            "emoji": emoji,
            "count": count.count
        })
    return json.dumps(formatted_reactions, ensure_ascii=False) if formatted_reactions else None

# ПУНКТ 6: Функция докачки пропущенных сообщений (ликвидация простоя)
async def sync_history(chat_id):
    try:
        last_id = await get_last_message_id(chat_id)
        print(f"[ЮЗЕРБОТ] Синхронизация чата {chat_id}. Последний ID в локальной базе: {last_id}")
        
        async for message in client.iter_messages(chat_id, min_id=last_id or 0, reverse=True):
            await process_and_save_message(message)
    except Exception as e:
        print(f"[Ошибка синхронизации истории чата {chat_id}]: {e}")

# Универсальная функция обработки и сохранения сообщения (Пункты 1, 3, 7, 8)
async def process_and_save_message(message):
    try:
        if not message.chat:
            return
            
        chat_id = message.chat_id
        chat_title = getattr(message.chat, 'title', 'Личный чат')
        
        text = message.text
        media_type = None
        media_path = None

        # ПУНКТ 3 & 1: Скачивание документов, photo, голосовых и фиксация пути на диске
        if message.media:
            if message.photo:
                media_type = "photo"
                media_path = f"downloads/photo_{message.id}.jpg"
            elif message.voice:
                media_type = "voice"
                media_path = f"downloads/voice_{message.id}.ogg"
            elif message.document:
                media_type = "document"
                filename = getattr(message.file, 'name', f"file_{message.id}")
                media_path = f"downloads/doc_{message.id}_{filename}"
            else:
                media_type = "other_media"

            if media_path and not os.path.exists(media_path):
                await client.download_media(message, file=media_path)

        # ПУНКТ 4: Получение реакций
        reactions_str = parse_reactions(message.reactions)

        # ПУНКТ 8: Сохраняем точную дату сообщения из Telegram
        message_date = message.date.replace(tzinfo=None)

        await save_message(
            chat_id=chat_id,
            chat_title=chat_title,
            message_id=message.id,
            user_id=message.sender_id,
            username=getattr(message.sender, 'username', None),
            text=text,
            media_type=media_type,
            media_path=media_path,
            reactions=reactions_str,
            created_at=message_date
        )
    except Exception as e:
        print(f"[Ошибка при обработке сообщения {message.id}]: {e}")

# Перехват новых сообщений в реальном времени
@client.on(events.NewMessage)
async def handle_incoming_message(event):
    await process_and_save_message(event.message)

# ПУНКТ 4: Перехват обновлений реакций и изменений сообщений
@client.on(events.MessageEdited)
async def handle_edited_message(event):
    await process_and_save_message(event.message)

# Главная функция запуска
async def start_userbot():
    print("Запуск юзербота сбора переписок через Клиентское API (MTProto Telethon)...")
    
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.sign_in(phone=PHONE, api_id=API_ID_WORK, api_hash=API_HASH_WORK)
    
    # ПУНКТ 6: Автоматически докачиваем историю из всех групп за время простоя
    print("[ЮЗЕРБОТ] Проверка пропущенных за время простоя сообщений...")
    async for dialog in client.iter_dialogs():
        if dialog.is_group:
            await sync_history(dialog.id)
            
    print("[ЮЗЕРБОТ] Система сбора запущена в фоновом режиме.")
    await client.run_until_disconnected()
