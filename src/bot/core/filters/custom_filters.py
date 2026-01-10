from aiogram.filters import Filter
from aiogram.types import CallbackQuery
from config.bot_config import ADMIN


class LegalInformationFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "⚖️ Правовая информация"


class SettingsFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "⚙️ Настройки"


class GetDBUsersFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "users 📄" and cb.from_user.id == ADMIN


class GetDBHashesFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "hashes 📄" and cb.from_user.id == ADMIN


class GetLogsFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "logs 📄" and cb.from_user.id == ADMIN


class GetSupportJournalFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "support 📄" and cb.from_user.id == ADMIN


class ScheduleStyle(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "🌌 Стиль расписания"


class BlockUserFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "🚫 Заблокировать" and cb.from_user.id == ADMIN


class SendMessageUserFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "Сообщение 👤" and cb.from_user.id == ADMIN


class SendMessageUsersFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "Сообщение 👥" and cb.from_user.id == ADMIN


class SendMessageGroupFilter(Filter):
    async def __call__(self, cb: CallbackQuery) -> bool:
        return cb.data == "Сообщение 🫂" and cb.from_user.id == ADMIN
