import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Параметры авторизации Юзербота (Спринт 2)
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")

# Параметры Бота Администратора
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")
# Преобразуем строку ID администраторов в список чисел
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# Формируем строку подключения к PostgreSQL для SQLAlchemy
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Ключи Yandex Cloud
YC_API_KEY = os.getenv("YC_API_KEY")
YC_FOLDER_ID = os.getenv("FOLDER_ID") # Либо YC_FOLDER_ID в зависимости от вашего .env
if not YC_FOLDER_ID:
    YC_FOLDER_ID = os.getenv("YC_FOLDER_ID")
