from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL

# Создаем асинхронный движок (Engine) для работы с PostgreSQL
engine = create_async_engine(DATABASE_URL, echo=False)

# Настраиваем фабрику асинхронных сессий
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

# Описываем модель таблицы для хранения сообщений
class MessageRecord(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, index=True)         # ID группы/канала
    chat_title = Column(String)                      # Название чата
    message_id = Column(BigInteger)                  # ID сообщения в Telegram
    user_id = Column(BigInteger, nullable=True)      # ID отправителя
    username = Column(String, nullable=True)         # Никнейм отправителя
    text = Column(Text, nullable=True)               # Текст сообщения
    media_type = Column(String, nullable=True)       # Тип вложения (photo, document и т.д.)
    reactions = Column(String, nullable=True)        # Реакции на сообщение (в формате JSON/строки)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # Время отправки (UTC)

# Функция для автоматического создания таблиц в PostgreSQL
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Функция для сохранения нового сообщения в БД
async def save_message(chat_id, chat_title, message_id, user_id, username, text, media_type=None, reactions=None):
    async with AsyncSessionLocal() as session:
        record = MessageRecord(
            chat_id=chat_id,
            chat_title=chat_title,
            message_id=message_id,
            user_id=user_id,
            username=username,
            text=text,
            media_type=media_type,
            reactions=reactions
        )
        session.add(record)
        await session.commit()

# Функция для выборки истории сообщений администратором (за определенный период)
async def get_chat_history(chat_id: int, start_date: datetime, end_date: datetime):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        stmt = select(MessageRecord).where(
            MessageRecord.chat_id == chat_id,
            MessageRecord.created_at >= start_date,
            MessageRecord.created_at <= end_date
        ).order_by(MessageRecord.created_at.asc())
        
        result = await session.execute(stmt)
        return result.scalars().all()
