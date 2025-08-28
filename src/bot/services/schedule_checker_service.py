import asyncio
import os
import random
import time
from datetime import datetime

import aiofiles
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile
from aiolimiter import AsyncLimiter
from config import themes_names
from config.paths import WORKSPACE
from phrases import no_schedule_for_date
from services.image_service import ImageCreator
from services.schedule_service import ScheduleService
from utils.formatters import format_error_message
from utils.hash import generate_hash
from utils.log import print_sent


class ScheduleChecker:
    """A class for tracking schedule appearances and changes"""

    SLEEP_NIGHT = 3600
    SLEEP_DAY = 60
    NIGHT_HOURS = (22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8)

    def __init__(self, bot, db_users, db_hashes):
        """Initializing necessary dependencies"""
        self.bot = bot
        self.db_users = db_users
        self.db_hashes = db_hashes
        self.schedule_service = ScheduleService()
        self.limiter = AsyncLimiter(10, 3)

    @classmethod
    async def is_night_time(cls) -> bool:
        """Checking whether the current hour is night"""
        return datetime.now().hour in cls.NIGHT_HOURS

    async def run_schedule_check(self) -> None:
        """Start tracking the appearance and schedule changes"""
        print("Проверка расписания запущена ✅ 🔄")
        iteration = 1
        try:
            while True:
                if await self.is_night_time():
                    print(f"🌙 Остановка проверки на 1ч (ночное время)")
                    print(f"Текущий час: {datetime.now().hour}")
                    self.db_hashes.cleanup_old_hashes()
                    await asyncio.sleep(self.SLEEP_NIGHT)
                    continue

                await self.process_schedule_updates()

                print(f"Ожидание... ⏳ I-{iteration}")
                iteration += 1
                await asyncio.sleep(self.SLEEP_DAY)

        except Exception as e:
            print(format_error_message(self.run_schedule_check.__name__, e))
            await asyncio.sleep(3)

    async def process_schedule_updates(self) -> None:
        """A method for schedule processing"""
        actual_dates = await self.schedule_service.get_dates_schedule()

        with open(f"{WORKSPACE}current_date.txt", "r") as file:
            current_dates = file.read().splitlines()

        print(f"{current_dates} - sended")
        print(f"{actual_dates} - actual")

        # Фильтрация новых дат, которые не были отправлены
        new_dates: list[str] = [
            date for date in actual_dates if date not in current_dates
        ]

        if new_dates:
            print(f"\n📆 Расписание появилось! {new_dates}")
            await self.handle_new_schedules(new_dates, actual_dates)

        updated_current_dates = list(
            set(current_dates) & set(actual_dates)
        )  # Только общие даты

        groups_schedule = await self.get_all_schedule(updated_current_dates)
        await self.check_schedule_change(groups_schedule)

    async def handle_new_schedules(
        self, new_dates: list[str], actual_dates: list[str]
    ) -> None:
        """A method for processing the schedule that appears"""
        groups_schedule = await self.get_all_schedule(
            new_dates
        )  # Получение расписания для каждой группы

        await self.check_schedule_change(
            groups_schedule
        )  # Добавление хешей расписания в базу данных

        start_send_time = time.time()

        await self.send_schedule(groups_schedule)  # Начало рассылки расписания

        end_send_time = time.time()

        with open(f"{WORKSPACE}current_date.txt", "w") as file:
            file.write("\n".join(actual_dates))

        print("\nРасписание отправлено ✅")
        print(f"Затраченное время: {end_send_time - start_send_time}")

    async def check_schedule_change(
        self, groups_schedule: dict[str, list[list]]
    ) -> None:
        """A method for tracking schedule changes"""
        try:
            for group_date, schedule in groups_schedule.items():
                data = group_date.split(" ")
                group = data[0]
                date = data[1]

                hash_value: str = await generate_hash(schedule)

                if self.db_hashes.check_hash_change(group, date, hash_value) == True:
                    print(f"Расписание у группы {group} - {date} изменилось")
                    await self.send_schedule({f"{group} {date}": schedule}, True)  # type: ignore

                elif self.db_hashes.check_hash_change(group, date, hash_value) == False:
                    continue
        except Exception as e:
            print(format_error_message(self.check_schedule_change.__name__, e))
            await asyncio.sleep(3)

    async def safe_send_photo(self, user_id: int, photo, updated: bool):
        """Method for sending schedule photos"""
        caption = "🆕 Расписание изменилось!" if updated else None

        attempt = 0
        while attempt <= 3:
            try:
                await self.bot.send_photo(
                    user_id,
                    photo=photo,
                    caption=caption,
                    disable_notification=bool(caption),
                )
                return True

            except TelegramRetryAfter as e:
                wait = float(e.retry_after) + 1.0 + random.random()
                attempt += 1

                print(f"Error RetryAfter - {wait}")
                await asyncio.sleep(wait)

            except Exception as e:
                attempt += 1
                print(f"\t\t🟥 attempt({attempt}) - Ошибка при отправке {user_id}")

    async def get_all_schedule(self, dates: list[str]) -> dict[str, list[list]]:
        """A method for getting a schedule for each group"""
        groups = await self.db_users.get_groups()

        coroutines = [
            self.schedule_service.get_schedule(group, date)
            for date in dates
            for group in groups
        ]

        keys = [f"{group} {date}" for group in groups for date in dates]

        results = []
        for coroutine in coroutines:
            response = await asyncio.create_task(coroutine)
            results.append(response)

        groups_schedule: dict[str, list[list]] = dict(zip(keys, results))

        return groups_schedule

    async def _get_themes_users(self, group: str) -> dict[str, list[int]]:
        """A method for getting users and their themes from a group"""
        themes_users: dict = {}
        users_id: list[int] = []

        for theme in themes_names:
            users_id: list[int] = await self.db_users.get_users_by_theme(group, theme)

            if any(users_id):
                themes_users[theme] = users_id
            else:
                continue

        return themes_users

    @staticmethod
    async def _create_photos_schedule(
        themes_users: dict[str, list[int]], schedule: list, date: str, group: str
    ) -> None:
        """A method for async creating a photo list"""
        tasks_create_photo = []
        for theme in themes_users:
            filename = f"{group}_{theme}"

            image_creator = ImageCreator()
            tasks_create_photo.append(
                image_creator.create_schedule_image(
                    data=schedule,
                    date=date,
                    number_rows=len(schedule) + 1,
                    filename=filename,
                    theme=theme,
                )
            )

        await asyncio.gather(*tasks_create_photo)

    @staticmethod
    async def _open_photos_schedule(
        themes_users: dict[str, list[int]], group: str
    ) -> dict[str, BufferedInputFile]:
        """Method for async opening of schedule photos"""
        open_photos = dict()
        for theme in themes_users:
            filename = f"{group}_{theme}"
            async with aiofiles.open(f"{WORKSPACE}{filename}.jpeg", "rb") as f:
                photo_data = await f.read()

            photo = BufferedInputFile(
                photo_data, filename=f"{WORKSPACE}{filename}.jpeg"
            )
            open_photos[theme] = photo

        return open_photos

    @staticmethod
    async def _get_user_chunks(
        themes_users: dict[str, list[int]],
    ) -> dict[str, list[list[int]]]:
        """A method for splitting users into chunks"""
        user_chunks_dict = dict()

        for theme, users_id in themes_users.items():
            chunk_size = 10
            user_chunks = [
                users_id[i : i + chunk_size]
                for i in range(0, len(users_id), chunk_size)
            ]

            user_chunks_dict[theme] = user_chunks

        return user_chunks_dict

    async def _send_no_schedule_message(self, users: list[int], group: str, date: str):
        """A method for sending a message about the absence of a schedule"""
        attempt = 0
        for user_id in users:
            async with self.limiter:
                while attempt <= 3:
                    try:
                        print(
                            f"\t\t{no_schedule_for_date.format(group=group, date=date)}"
                        )
                        await self.bot.send_message(
                            user_id,
                            no_schedule_for_date.format(group=group, date=date),
                            parse_mode="HTML",
                            disable_notification=True,
                        )
                        break

                    except TelegramRetryAfter as e:
                        wait = float(e.retry_after) + 1.0 + random.random()
                        attempt += 1

                        print(f"Error RetryAfter - {wait}")
                        await asyncio.sleep(wait)

                    except Exception as e:
                        attempt += 1
                        print(
                            f"\t\t🟥 attempt({attempt}) - Ошибка при отправке {user_id} - {group}"
                        )

    async def _send_schedule(
        self,
        user_chunks_dict: dict[str, list[list[int]]],
        open_photos: dict[str, BufferedInputFile],
        updated_schedule: bool,
    ) -> None:
        """A method for sending schedule photos by chunks"""
        for theme, user_chunks in user_chunks_dict.items():
            photo = open_photos[theme]

            for chunk in user_chunks:
                tasks = []
                for user_id in chunk:
                    tasks.append(self.safe_send_photo(user_id, photo, updated_schedule))
                    tasks.append(print_sent(user_id))

                for task in tasks:
                    async with self.limiter:
                        await asyncio.create_task(task)

    async def send_schedule(
        self,
        groups_schedule: dict[str, list[list]],
        updated_schedule: bool = False,
    ) -> None:
        """The method for sending the schedule"""
        try:
            # | groups_schedule: { "group date": list[list[...]] }

            for group_date, schedule in groups_schedule.items():
                data = group_date.split(" ")
                group = data[0]
                date = data[1]

                users: list[int] = await self.db_users.get_users_by_group(group)

                print(f"group: {group}")
                print(f"date: {date}")
                print(f"users: {users}")

                if not any(schedule):
                    await self._send_no_schedule_message(users, group, date)
                    continue

                themes_users = await self._get_themes_users(group)

                await self._create_photos_schedule(themes_users, schedule, date, group)

                open_photos = await self._open_photos_schedule(themes_users, group)

                user_chunks_dict: dict[str, list[list[int]]] = (
                    await self._get_user_chunks(themes_users)
                )

                await self._send_schedule(
                    user_chunks_dict, open_photos, updated_schedule
                )

                for theme in themes_users:
                    filename = f"{group}_{theme}.jpeg"
                    (
                        os.remove(f"{WORKSPACE}{filename}")
                        if os.path.exists(f"{WORKSPACE}{filename}")
                        else False
                    )

        except Exception as e:
            print(format_error_message(self.send_schedule.__name__, e))
