"""
Dependency injection container for managing global bot objects.

This module contains a container for storing and accessing global bot objects
and the database manager. It provides centralized dependency management
with lazy initialization.
"""

from aiogram import Bot

from services.database import DatabaseManager

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
