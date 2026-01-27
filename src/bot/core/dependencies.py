from aiogram import Bot

from bot.services.database import DatabaseManager


class Container:
    _bot: Bot | None = None
    _db_manager: DatabaseManager | None = None

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            raise RuntimeError("Bot not initialized!")
        return self._bot

    @property
    def db_manager(self) -> DatabaseManager:
        if self._db_manager is None:
            raise RuntimeError("DatabaseManager not initialized!")
        return self._db_manager


container = Container()
