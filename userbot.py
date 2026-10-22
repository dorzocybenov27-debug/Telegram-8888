import os
import json
import importlib
from datetime import datetime
from telethon import TelegramClient, events, functions, types as tl_types
from config import API_ID, API_HASH, PHONE  # Подгружаем настройки
# ИСПРАВЛЕНО: Добавлен импорт get_monitored_chats для фильтрации личных диалогов
from database import save_message, get_last_message_id, get_monitored_chats

# Создаем базовую папку для медиафайлов
os.makedirs("downloads", exist_ok=True)

# Ваши личные ключи приложения (с сайта my.telegram.org)
API_ID_WORK = 33489928
API_HASH_WORK = "c8027f90a8ae98283e6bc4f3f6044e8b"

# Динамический безопасный импорт класса обфускации для обхода AssertionError
try:
    mod = importlib.import_module("telethon.network.connection.tcpobfuscated")
    ObfuscatedConnection = getattr(mod, "ConnectionTcpObfuscated")
except ImportError:
    mod = importlib.import_module("telethon.network.connection.tcp.tcpobfuscated")
    ObfuscatedConnection = getattr(mod, "ConnectionTcpObfuscated")

# Интегрирована русская локализация для стабильной отправки кода
client = TelegramClient(
    "session_collector", 
    API_ID_WORK, 
    API_HASH_WORK, 
    connection=ObfuscatedConnection,
    lang_code="ru", 
    system_lang_code="ru-RU"
)


# Функция для парсинга реакций, их количества и авторов (Пункт 4)
def parse_reactions(reactions_data):
    if not reactions_data:
        return None
    
    try:
        formatted_reactions = []
        
        # Парсинг стандартной структуры метаданных реакций Telethon
        if hasattr(reactions_data, 'results') and reactions_data.results:
            for count in reactions_data.results:
                if hasattr(count, 'reaction') and count.reaction:
                    emoji = count.reaction.emoticon if hasattr(count.reaction, 'emoticon') else "custom_emoji"
                    formatted_reactions.append({
                        "emoji": emoji,
                        "count": count.count
                    })
        
        # Резервный парсинг для альтернативных структур (защита от AttributeError в асинхронных событиях)
        elif hasattr(reactions_data, 'reactions') and reactions_data.reactions:
            for r in reactions_data.reactions:
                if hasattr(r, 'emoji') and r.emoji:
                    formatted_reactions.append({"emoji": r.emoji, "count": 1})
        
        return json.dumps(formatted_reactions, ensure_ascii=False) if formatted_reactions else None
        
    except Exception as e:
        print(f"[Предупреждение]: Не удалось извлечь метаданные реакций: {e}")
        return None

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
        temp_path = None

        # ПУНКТ 3 & 1: Скачивание документов, photo, голосовых и фиксация пути на диске
        if message.media:
            if message.photo:
                media_type = "photo"
                temp_path = f"downloads/photo_{message.id}.jpg"
            elif message.voice:
                media_type = "voice"
                temp_path = f"downloads/voice_{message.id}.ogg"
            elif message.document:
                media_type = "document"
                filename = getattr(message.file, 'name', f"file_{message.id}")
                temp_path = f"downloads/doc_{message.id}_{filename}"
            else:
                media_type = "other_media"

        # ПУНКТ 4: Получение реакций
        reactions_str = parse_reactions(message.reactions)

        # ПУНКТ 8: Сохраняем точную дату сообщения из Telegram
        message_date = message.date.replace(tzinfo=None)

        # database.py сама создаст именную папку группы и вернет правильный final_path
        final_path = await save_message(
            chat_id=chat_id,
            chat_title=chat_title,
            message_id=message.id,
            user_id=message.sender_id,
            username=getattr(message.sender, 'username', None),
            text=text,
            media_type=media_type,
            media_path=temp_path,
            reactions=reactions_str,
            created_at=message_date
        )

        # Физически скачиваем исторический медиафайл строго в именную подпапку группы
        if temp_path and final_path and not os.path.exists(final_path):
            await client.download_media(message, file=final_path)

    except Exception as e:
        print(f"[Ошибка при обработке сообщения {message.id}]: {e}")

# ИСПРАВЛЕНО: Перехват новых сообщений в реальном времени с жестким фильтром групп бота
@client.on(events.NewMessage)
async def handle_incoming_message(event):
    try:
        monitored_ids = await get_monitored_chats()
        # Если чата нет в белом списке базы данных, полностью игнорируем его активность
        if event.chat_id not in monitored_ids:
            return
        await process_and_save_message(event.message)
    except Exception as e:
        print(f"[Ошибка фильтрации входящего сообщения]: {e}")

# ИСПРАВЛЕНО: Перехват обновлений реакций и изменений с жестким фильтром групп бота
@client.on(events.MessageEdited)
async def handle_edited_message(event):
    try:
        monitored_ids = await get_monitored_chats()
        # Игнорируем изменения реакций/сообщений в сторонних личных чатах
        if event.chat_id not in monitored_ids:
            return
        await process_and_save_message(event.message)
    except Exception as e:
        print(f"[Ошибка фильтрации изменения сообщения]: {e}")

# Главная функция запуска
async def start_userbot():
    print("Запуск юзербота сбора переписок через Клиентское API (MTProto Telethon)...")
    
    await client.connect()
    
    if not await client.is_user_authorized():
        try:
            await client.send_code_request(phone=PHONE, force_sms=False)
        except Exception as e:
            print(f"[ЮЗЕРБОТ] Ошибка первичного запроса кода, пробуем стандартный метод: {e}")
            await client.send_code_request(phone=PHONE)
            
        code = input('Пожалуйста, введите код из Telegram: ')
        try:
            await client.sign_in(phone=PHONE, code=code)
        except Exception as e:
            password = input('На вашем аккаунте включен облачный пароль. Введите его: ')
            await client.sign_in(password=password)

    # Автоматически докачиваем историю ТОЛЬКО из чатов мониторинга
    print("[ЮЗЕРБОТ] Проверка групп, находящихся на мониторинге...")
    monitored_ids = await get_monitored_chats()
    
    print(f"[ЮЗЕРБОТ] Найдено чатов для синхронизации: {len(monitored_ids)}")
    for target_id in monitored_ids:
        await sync_history(target_id)
            
    print("[ЮЗЕРБОТ] Система точечного сбора запущена в фоновом режиме.")
    await client.run_until_disconnected()
