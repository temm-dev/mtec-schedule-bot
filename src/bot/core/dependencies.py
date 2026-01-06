from aiogram import Bot
from services.database import DatabaseHashes, DatabaseScheduleArchive, DatabaseUsers


class Container:
    _bot: Bot | None = None
    _db_users: DatabaseUsers | None = None
    _db_hashes: DatabaseHashes | None = None
    _db_schedule_archive: DatabaseScheduleArchive | None = None

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            raise RuntimeError("Bot not initialized!")
        return self._bot

    @property
    def db_users(self) -> DatabaseUsers:
        if self._db_users is None:
            raise RuntimeError("Database not initialized!")
        return self._db_users

    @property
    def db_hashes(self) -> DatabaseHashes:
        if self._db_hashes is None:
            raise RuntimeError("Database not initialized!")
        return self._db_hashes

    @property
    def db_schedule_archive(self) -> DatabaseScheduleArchive:
        if self._db_schedule_archive is None:
            raise RuntimeError("Database not initialized!")
        return self._db_schedule_archive


container = Container()
