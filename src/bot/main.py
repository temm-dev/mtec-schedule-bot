import asyncio
import logging
import os

import aiofiles
import coloredlogs
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.bot_config import TOKEN
from config.paths import WORKSPACE
from core.dependencies import container
from services.schedule_checker_service import ScheduleChecker
from services.schedule_service import ScheduleService

from bot.services.database import db_manager

coloredlogs.install(level="INFO", fmt="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

os.mkdir(f"{WORKSPACE}") if not os.path.exists(f"{WORKSPACE}") else False
if not os.path.exists(f"{WORKSPACE}blacklist.txt"):
    with open(f"{WORKSPACE}blacklist.txt", "w") as file:
        pass


async def main():
    async with aiofiles.open(f"{WORKSPACE}current_date.txt", "w") as file:
        await file.write("\n".join(await ScheduleService().get_dates_schedule()))

    # Initializing the bot
    container._bot = Bot(token=TOKEN)
    await container._bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот инициализирован")

    # Database initialization
    container._db_manager = db_manager
    await db_manager.init_db()

    # Initializing the schedule checker service
    schedule_checker = ScheduleChecker(container.bot, container.db_manager)
    asyncio.create_task(schedule_checker.run_schedule_check())
    print("✅ Проверка расписания запущена")

    # Initializing handlers
    from core.handlers import setup_handlers

    dp = Dispatcher(storage=MemoryStorage())
    setup_handlers(dp)

    print("✅ Бот запущен")
    await dp.start_polling(container.bot)


if __name__ == "__main__":
    asyncio.run(main())
