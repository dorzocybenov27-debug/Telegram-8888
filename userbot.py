import json
from telethon import TelegramClient, events
from config import API_ID, API_HASH
from database import save_message

# Инициализируем клиент Telethon. Сессия сохранится в файл session_collector.session
client = TelegramClient("session_collector", API_ID, API_HASH)

@client.on(events.NewMessage)
async def handle_new_message(event):
    # Фильтруем сообщения: собираем только из групповых чатов и каналов (не личные переписки)
    if not event.is_private:
        try:
            chat = await event.get_chat()
            sender = await event.get_sender()

            # Извлекаем данные отправителя
            user_id = sender.id if sender else None
            username = sender.username if sender and hasattr(sender, "username") else None

            # Извлекаем текст сообщения
            text = event.message.message

            # Проверяем наличие медиафайлов (картинки, документы, видео)
            media_type = None
            if event.message.media:
                media_type = type(event.message.media).__name__

            # Обрабатываем реакции, если они присутствуют на сообщении
            reactions_str = None
            if event.message.reactions:
                reactions_list = []
                for r in event.message.reactions.results:
                    # Если реакция — это стандартный эмодзи
                    if hasattr(r.reaction, "emoticon"):
                        reactions_list.append(r.reaction.emoticon)
                    # Если это кастомный премиум-эмодзи
                    elif hasattr(r.reaction, "document_id"):
                        reactions_list.append(f"custom_{r.reaction.document_id}")
                
                if reactions_list:
                    reactions_str = json.dumps(reactions_list)

            # Сохраняем собранные данные в PostgreSQL через наш модуль базы данных
            await save_message(
                chat_id=event.chat_id,
                chat_title=getattr(chat, "title", "Групповой чат"),
                message_id=event.message.id,
                user_id=user_id,
                username=username,
                text=text,
                media_type=media_type,
                reactions=reactions_str
            )
        except Exception as e:
            print(f"Ошибка при обработке сообщения юзерботом: {e}")

async def start_userbot():
    print("Запуск юзербота для сбора корпоративных переписок...")
    await client.start()
    print("Юзербот успешно авторизован и запущен.")
    await client.run_until_disconnected()
