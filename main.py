import asyncio
from database import init_db
from admin_bot import start_admin_bot
from userbot import start_userbot

async def main():
    print("=== Инициализация системы Спринта №2 ===")
    # Инициализируем таблицы базы данных v2
    await init_db()
    
    print("Запуск параллельных асинхронных сервисов Telegram...")
    # ПУНКТ 6: Запускаем одновременно админ-бота и юзербота
    await asyncio.gather(
        start_admin_bot(),
        start_userbot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n[INFO] Система сбора корпоративных переписок остановлена.")
