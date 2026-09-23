import asyncio
from database import init_db
from userbot import start_userbot
from admin_bot import start_admin_bot

async def main():
    print("=== Инициализация системы сбора переписок ===")
    
    # Шаг 1: Автоматическая проверка и создание таблиц в PostgreSQL
    try:
        await init_db()
        print("База данных PostgreSQL успешно инициализирована.")
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к БД: {e}")
        print("Проверьте настройки DB_USER, DB_PASSWORD и запущен ли сервер PostgreSQL.")
        return

    # Шаг 2: Одновременный асинхронный запуск двух Telegram-модулей
    print("Запуск асинхронных сервисов Telegram...")
    await asyncio.gather(
        start_userbot(),    # Логирует сообщения из чатов (Telethon MTProto API)
        start_admin_bot()   # Отвечает администраторам на команды (Aiogram Bot API)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nСистема остановлена пользователем.")
