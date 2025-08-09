import asyncio
import logging
import os

import coloredlogs
from aiogram import Bot, Dispatcher
from config.bot_config import TOKEN
from config.paths import WORKSPACE, PATH_DBs
from core.dependencies import container
from services.database import DatabaseHashes, DatabaseUsers
from services.schedule_checker_service import ScheduleChecker
from services.schedule_service import ScheduleService

coloredlogs.install(level="INFO", fmt="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

os.mkdir(f"{WORKSPACE}") if not os.path.exists(f"{WORKSPACE}") else False

if not os.path.exists(f"{WORKSPACE}blacklist.txt"):
    with open(f"{WORKSPACE}blacklist.txt", "w") as file:
        pass

with open(f"{WORKSPACE}current_date.txt", "w") as file:
    file.write("\n".join(asyncio.run(ScheduleService().get_dates_schedule())))


async def main():
    container._bot = Bot(token=TOKEN)
    container._db_users = DatabaseUsers(f"{PATH_DBs}DB.db")
    container._db_hashes = DatabaseHashes(f"{PATH_DBs}schedule_hashes.db")

    from core.handlers import setup_handlers

    dp = Dispatcher()
    setup_handlers(dp)

    print("START CHECK SCHEDULE 🤖")
    schedule_checker = ScheduleChecker(
        container.bot, container.db_users, container.db_hashes
    )
    asyncio.create_task(schedule_checker.run_schedule_check())

    print("START HANDLERS 🤖")
    await dp.start_polling(container.bot)


if __name__ == "__main__":
    asyncio.run(main())
