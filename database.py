import os
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, Text, UniqueConstraint, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL

# Инициализация асинхронного движка SQLAlchemy для PostgreSQL
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class CorporateMessage(Base):
    __tablename__ = 'corporate_messages_v2'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    chat_title = Column(String, nullable=True)
    message_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    username = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    media_type = Column(String, nullable=True)
    media_path = Column(String, nullable=True)  # ПУНКТ 3: Хранение пути к файлу на диске
    reactions = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False) # ПУНКТ 8: Время самого сообщения

    # ПУНКТ 7: Уникальное ограничение на связку Чат + Сообщение для исключения дубликатов
    __table_args__ = (
        UniqueConstraint('chat_id', 'message_id', name='_chat_message_uc'),
    )

async def init_db():
    async with engine.begin() as conn:
        # Автоматическое создание таблиц с новыми индексами
        await conn.run_sync(Base.metadata.create_all)
    print("База данных PostgreSQL успешно инициализирована.")

async def save_message(chat_id, chat_title, message_id, user_id, username, text, media_type, media_path, reactions, created_at):
    async with AsyncSessionLocal() as session:
        try:
            # ПУНКТ 7: Проверка методом "Добавить или обновить" (Upsert) для предотвращения дублирования
            stmt = select(CorporateMessage).where(
                CorporateMessage.chat_id == chat_id,
                CorporateMessage.message_id == message_id
            )
            result = await session.execute(stmt)
            existing_msg = result.scalar_one_or_none()

            if existing_msg:
                # Если сообщение уже есть (например, обновился текст или медиа), обновляем его данные
                existing_msg.text = text
                existing_msg.reactions = reactions
                existing_msg.media_path = media_path
            else:
                # Если сообщения нет, создаем новую уникальную запись
                new_msg = CorporateMessage(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    message_id=message_id,
                    user_id=user_id,
                    username=username,
                    text=text,
                    media_type=media_type,
                    media_path=media_path,
                    reactions=reactions,
                    created_at=created_at
                )
                session.add(new_msg)
            
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e

async def get_chat_history(chat_id: int, start_date: datetime, end_date: datetime):
    async with AsyncSessionLocal() as session:
        # Извлечение истории строго по валидированному временному диапазону
        stmt = (
            select(CorporateMessage)
            .where(
                CorporateMessage.chat_id == chat_id,
                CorporateMessage.created_at >= start_date,
                CorporateMessage.created_at <= end_date
            )
            .order_by(CorporateMessage.created_at.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()
async def get_last_message_id(chat_id: int):
    async with AsyncSessionLocal() as session:
        # Ищем максимальный message_id для конкретного чата в нашей базе v2
        stmt = (
            select(CorporateMessage.message_id)
            .where(CorporateMessage.chat_id == chat_id)
            .order_by(CorporateMessage.message_id.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
