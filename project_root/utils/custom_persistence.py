import logging
from typing import Dict, Any, Optional, Tuple, cast
from collections import defaultdict
from copy import deepcopy

from telegram.ext import BasePersistence
from services.database_service import DatabaseService, database_service

logger = logging.getLogger(__name__)

class SQLAlchemyPersistence(BasePersistence):
    """
    A persistence class that uses SQLAlchemy for storing bot data.
    It loads all data into memory on initialization and flushes it back to the DB.
    """

    def __init__(self, db_service: DatabaseService):
        super().__init__(store_user_data=True, store_chat_data=True, store_bot_data=True)
        self.db_service = db_service
        self.user_data: Optional[Dict[int, Dict[str, Any]]] = None
        self.chat_data: Optional[Dict[int, Dict[str, Any]]] = None
        self.bot_data: Optional[Dict[str, Any]] = None
        self.conversations: Optional[Dict[str, Dict[Tuple, Any]]] = None
        self._is_loaded = False

    async def _load_data_if_needed(self):
        """Load data from the database if it hasn't been loaded yet."""
        if self._is_loaded:
            return

        logger.debug("Loading persistence data from database.")
        data = await self.db_service.get_persistence_data()

        self.user_data = defaultdict(dict, data.get("user_data", {}))
        self.chat_data = defaultdict(dict, data.get("chat_data", {}))
        self.bot_data = defaultdict(dict, data.get("bot_data", {}))
        self.conversations = defaultdict(dict, data.get("conversations", {}))

        self._is_loaded = True
        logger.debug("Persistence data loaded successfully.")

    async def get_user_data(self) -> Dict[int, Dict[str, Any]]:
        await self._load_data_if_needed()
        return deepcopy(cast(Dict, self.user_data))

    async def get_chat_data(self) -> Dict[int, Dict[str, Any]]:
        await self._load_data_if_needed()
        return deepcopy(cast(Dict, self.chat_data))

    async def get_bot_data(self) -> Dict[str, Any]:
        await self._load_data_if_needed()
        return deepcopy(cast(Dict, self.bot_data))

    async def get_conversations(self, name: str) -> Dict:
        await self._load_data_if_needed()
        return deepcopy(cast(Dict, self.conversations).get(name, {}))

    async def update_user_data(self, user_id: int, data: Dict[str, Any]) -> None:
        if self.user_data is not None:
            self.user_data[user_id] = data

    async def update_chat_data(self, chat_id: int, data: Dict[str, Any]) -> None:
        if self.chat_data is not None:
            self.chat_data[chat_id] = data

    async def update_bot_data(self, data: Dict[str, Any]) -> None:
        self.bot_data = data

    async def update_conversation(
        self, name: str, key: Tuple[int, ...], new_state: Optional[object]
    ) -> None:
        if self.conversations is not None:
            if new_state is None:
                self.conversations.get(name, {}).pop(key, None)
            else:
                if name not in self.conversations:
                    self.conversations[name] = {}
                self.conversations[name][key] = new_state

    async def flush(self) -> None:
        """Saves all data to the database."""
        if not self._is_loaded:
            return

        logger.debug("Flushing persistence data to database.")
        data_to_save = {
            "user_data": self.user_data,
            "chat_data": self.chat_data,
            "bot_data": self.bot_data,
            "conversations": self.conversations,
        }
        await self.db_service.update_persistence_data(data_to_save)
        logger.debug("Persistence data flushed successfully.")

    async def get_callback_data(self) -> Optional[Dict]:
        return None  # Not implemented

    async def update_callback_data(self, data: Dict) -> None:
        pass  # Not implemented

# A singleton instance to be used by the bot
sqlalchemy_persistence = SQLAlchemyPersistence(database_service)