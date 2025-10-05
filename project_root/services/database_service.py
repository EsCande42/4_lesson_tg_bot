import asyncio
import json
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import select, update
from typing import Optional, Dict, Any, List, Tuple
from utils.database import User, UserSettings, ImageSettings, Message, PersistenceData, init_db
from collections import defaultdict

def _str_to_tuple(s: str) -> Tuple[int, ...]:
    """Converts a string representation of a tuple back to a tuple."""
    # This handles cases like '(123,)' and '(123, 456)'
    return tuple(map(int, s.strip('()').split(',')))

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
                    raise ValueError("User not found")
                settings = session.query(UserSettings).filter_by(user_id=user.id).first()
                if not settings:
                    settings = UserSettings(user_id=user.id)
                    session.add(settings)
                    session.commit()
                    session.refresh(settings)
                return {k: v for k, v in settings.__dict__.items() if not k.startswith('_')}
        return await self._execute_sync(_get_settings)

    async def update_user_settings(self, user_id: int, new_settings: Dict[str, Any]):
        def _update():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                session.query(UserSettings).filter_by(user_id=user.id).update(new_settings)
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
                return {k: v for k, v in settings.__dict__.items() if not k.startswith('_')}
        return await self._execute_sync(_get_settings)

    async def update_image_settings(self, user_id: int, new_settings: Dict[str, Any]):
        def _update():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                session.query(ImageSettings).filter_by(user_id=user.id).update(new_settings)
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

    async def get_message_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        def _get_history():
            with self.Session() as session:
                user = session.query(User).filter_by(telegram_id=user_id).one()
                messages = session.query(Message).filter_by(user_id=user.id).order_by(Message.timestamp.desc()).limit(limit).all()
                return [{"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in reversed(messages)]
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
                stmt = select(PersistenceData)
                records = session.execute(stmt).scalars().all()

                data = {
                    "user_data": defaultdict(dict),
                    "chat_data": defaultdict(dict),
                    "bot_data": {},
                    "conversations": defaultdict(dict),
                }

                for record in records:
                    if record.data_type == "user":
                        data["user_data"][int(record.data_key)] = record.data
                    elif record.data_type == "chat":
                        data["chat_data"][int(record.data_key)] = record.data
                    elif record.data_type == "bot":
                        data["bot_data"] = record.data
                    elif record.data_type == "conversation":
                        # Keys are conversation names, values are dicts of {tuple_key: state}
                        conv_name = record.data_key
                        conv_data = {_str_to_tuple(k): v for k, v in record.data.items()}
                        data["conversations"][conv_name] = conv_data
                return data
        return await self._execute_sync(_get_data)

    async def update_persistence_data(self, data: Dict[str, Any]):
        def _update_data():
            with self.Session() as session:
                # User Data
                for key, value in data.get("user_data", {}).items():
                    session.merge(PersistenceData(data_type="user", data_key=str(key), data=value))
                # Chat Data
                for key, value in data.get("chat_data", {}).items():
                    session.merge(PersistenceData(data_type="chat", data_key=str(key), data=value))
                # Bot Data
                bot_data = data.get("bot_data")
                if bot_data:
                     session.merge(PersistenceData(data_type="bot", data_key="bot", data=bot_data))
                # Conversations
                conversations = data.get("conversations", {})
                for conv_name, conv_data in conversations.items():
                    # Convert tuple keys to strings for JSON
                    serializable_data = {str(k): v for k, v in conv_data.items()}
                    session.merge(PersistenceData(data_type="conversation", data_key=conv_name, data=serializable_data))

                session.commit()
        return await self._execute_sync(_update_data)

# Singleton instance
db_session_factory = init_db()
database_service = DatabaseService(db_session_factory)