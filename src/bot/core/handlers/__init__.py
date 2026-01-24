from aiogram import Dispatcher

from ..middlewares.antispam import AntiSpamMiddleware
from ..middlewares.blacklist import BlacklistMiddleware
from .admin import register as register_admin_handlers
from .common import register as register_common_handlers
from .journal import register as register_journal_handlers
from .schedule import register as register_schedule_handlers
from .setting import register as register_setting_handlers


def setup_handlers(dp: Dispatcher):
    register_admin_handlers(dp)
    register_common_handlers(dp)
    register_journal_handlers(dp)
    register_schedule_handlers(dp)
    register_setting_handlers(dp)

    dp.message.middleware(AntiSpamMiddleware())
    dp.message.middleware(BlacklistMiddleware())
