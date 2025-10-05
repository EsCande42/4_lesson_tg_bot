import asyncio
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, Dict, Any, List
from utils.database import User, UserSettings, ImageSettings, Message, init_db

class DatabaseService:
    def __init__(self, session_factory: sessionmaker):
        self.Session = session_factory

    def _execute_sync(self, func, *args, **kwargs):
        """Helper to run sync DB operations in a thread."""
        return asyncio.to_thread(func, *args, **kwargs)

    async def get_or_create_user(self, telegram_id: int, **kwargs) -> User:
        def _get_or_create():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if not user:
                    user = User(telegram_id=telegram_id, **kwargs)
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                return user
        return await self._execute_sync(_get_or_create)

    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        def _get_settings():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                if not user:
                    # This case should ideally be handled by get_or_create_user first
                    raise ValueError("User not found")

                settings = session.query(UserSettings).filter_by(user_id=user.id).first()
                if not settings:
                    settings = UserSettings(user_id=user.id)
                    session.add(settings)
                    session.commit()
                    session.refresh(settings)

                return {
                    'base_url': settings.base_url,
                    'model': settings.model,
                    'temperature': settings.temperature,
                    'max_tokens': settings.max_tokens,
                    'use_assistant': settings.use_assistant,
                    'assistant_url': settings.assistant_url
                }
        return await self._execute_sync(_get_settings)

    async def update_user_settings(self, user_id: int, new_settings: Dict[str, Any]):
        def _update():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                settings = session.query(UserSettings).filter_by(user_id=user.id).one()
                for key, value in new_settings.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                session.commit()
        await self._execute_sync(_update)

    async def get_image_settings(self, user_id: int) -> Dict[str, Any]:
        def _get_settings():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).first()
                if not user:
                    raise ValueError("User not found")

                settings = session.query(ImageSettings).filter_by(user_id=user.id).first()
                if not settings:
                    settings = ImageSettings(user_id=user.id)
                    session.add(settings)
                    session.commit()
                    session.refresh(settings)

                return {
                    'base_url': settings.base_url,
                    'model': settings.model,
                    'size': settings.size,
                    'quality': settings.quality,
                    'style': settings.style,
                    'hdr': settings.hdr
                }
        return await self._execute_sync(_get_settings)

    async def update_image_settings(self, user_id: int, new_settings: Dict[str, Any]):
        def _update():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                settings = session.query(ImageSettings).filter_by(user_id=user.id).one()
                for key, value in new_settings.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                session.commit()
        await self._execute_sync(_update)

    async def add_message_to_history(self, user_id: int, role: str, content: str):
        def _add_message():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                message = Message(user_id=user.id, role=role, content=content)
                session.add(message)
                session.commit()
        await self._execute_sync(_add_message)

    async def get_message_history(self, user_id: int, limit: int = 10) -> List[Dict[str, str]]:
        def _get_history():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                messages = (
                    session.query(Message)
                    .filter_by(user_id=user.id)
                    .order_by(Message.timestamp.desc())
                    .limit(limit)
                    .all()
                )
                # Return in chronological order
                return [
                    {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                    for m in reversed(messages)
                ]
        return await self._execute_sync(_get_history)

    async def clear_message_history(self, user_id: int):
        def _clear_history():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                session.query(Message).filter_by(user_id=user.id).delete()
                session.commit()
        await self._execute_sync(_clear_history)

    async def get_persistence_data(self) -> Dict[str, Any]:
        def _get_data():
            with self.Session() as session:
                data = {
                    "user_data": defaultdict(dict),
                    "chat_data": defaultdict(dict),
                    "bot_data": {},
                    "conversations": defaultdict(dict)
                }

                all_persistence = session.query(PersistenceData).all()
                for record in all_persistence:
                    if record.user_id:
                        data["user_data"][record.user_id] = record.user_data or {}
                    if record.chat_id:
                        data["chat_data"][record.chat_id] = record.chat_data or {}
                    if record.bot_data: # Assuming one row for bot_data
                        data["bot_data"] = record.bot_data or {}

                return data

        return await self._execute_sync(_get_data)

    async def update_persistence_data(self, data: Dict[str, Any]):
        def _update_data():
            with self.Session() as session:
                # Update user_data
                for user_id, user_data in data.get("user_data", {}).items():
                    record = session.query(PersistenceData).filter_by(user_id=user_id).first()
                    if not record:
                        record = PersistenceData(user_id=user_id)
                        session.add(record)
                    record.user_data = user_data

                # Update chat_data
                for chat_id, chat_data in data.get("chat_data", {}).items():
                    record = session.query(PersistenceData).filter_by(chat_id=chat_id).first()
                    if not record:
                        record = PersistenceData(chat_id=chat_id)
                        session.add(record)
                    record.chat_data = chat_data

                # Update bot_data (assuming a single record, e.g., with a null user/chat id)
                bot_data = data.get("bot_data")
                if bot_data:
                    record = session.query(PersistenceData).filter_by(user_id=None, chat_id=None).first()
                    if not record:
                        record = PersistenceData()
                        session.add(record)
                    record.bot_data = bot_data

                session.commit()

        await self._execute_sync(_update_data)


# Singleton instance
db_session_factory = init_db()
database_service = DatabaseService(db_session_factory)