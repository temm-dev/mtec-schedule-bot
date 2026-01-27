import asyncio
import gc
import os
import random
import time
from datetime import datetime

import aiofiles
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile, FSInputFile
from aiolimiter import AsyncLimiter
from config import themes_names
from config.paths import WORKSPACE
from phrases import no_schedule_mentor_text, no_schedule_text
from services.image_service import ImageCreator
from services.schedule_service import ScheduleService
from utils.formatters import format_error_message
from utils.hash import generate_hash
from utils.log import print_sent
from utils.utils import day_week_by_date

from bot.services.database import ChatRepository, ScheduleArchiveRepository, ScheduleHashRepository, UserRepository


class ScheduleChecker:
    """A class for tracking schedule appearances and changes"""

    SLEEP_NIGHT = 3600
    SLEEP_DAY = 180
    NIGHT_HOURS = (22, 23, 0, 1, 2, 3, 4, 5, 6, 7)

    def __init__(self, bot, db_manager):
        """Initializing necessary dependencies"""
        self.bot = bot
        self.db_manager = db_manager
        self.schedule_service = ScheduleService()
        self.limiter = AsyncLimiter(15, 7)

    @classmethod
    async def is_night_time(cls) -> bool:
        """Checking whether the current hour is night"""
        return datetime.now().hour in cls.NIGHT_HOURS

    async def run_schedule_check(self) -> None:
        """Start tracking the appearance and schedule changes"""
        iteration = 1
        try:
            while True:
                if await self.is_night_time():
                    print(f"🌙 Остановка проверки на 1ч (ночное время)")
                    print(f"Текущий час: {datetime.now().hour}")

                    async for session in self.db_manager.get_session():  # type: ignore
                        await ScheduleHashRepository.cleanup_old_hashes(session)

                    gc.collect()
                    gc.collect()
                    print(f"🗑️ Мусор очищен!")
                    await asyncio.sleep(self.SLEEP_NIGHT)
                    continue

                await self.process_schedule_updates()

                print(f"Ожидание... ⏳ I-{iteration}")
                iteration += 1
                await asyncio.sleep(self.SLEEP_DAY)
        except Exception as e:
            print(format_error_message(self.run_schedule_check.__name__, e))
            await asyncio.sleep(3)

    async def process_update_archive(self, dates: list) -> None:
        async with aiofiles.open(f"{WORKSPACE}all_groups.txt", "r") as file:
            content = await file.read()
            groups = list(set(content.splitlines()))

        async with aiofiles.open(f"{WORKSPACE}all_mentors.txt", "r") as file:
            content = await file.read()
            mentors = list(set(content.splitlines()))

        print("Начало добавления расписания в архив")

        for date in dates:
            for group in groups:
                schedule = await self.schedule_service.get_schedule(group, date)
                if not schedule:
                    continue
                hash_value: str = await generate_hash(schedule)

                async for session in self.db_manager.get_session():  # type: ignore
                    await ScheduleArchiveRepository.update_student_schedule(session, date, group, schedule, hash_value)

            for mentor in mentors:
                schedule = await self.schedule_service.get_mentors_schedule(mentor, date)
                if not schedule:
                    continue
                hash_value: str = await generate_hash(schedule)

                async for session in self.db_manager.get_session():  # type: ignore
                    await ScheduleArchiveRepository.update_mentor_schedule(session, date, mentor, schedule, hash_value)

    async def process_schedule_updates(self) -> None:
        """A method for schedule processing"""
        actual_dates = await self.schedule_service.get_dates_schedule()
        actual_current_dates = await self.schedule_service.get_actual_current_dates()

        # Добавление расписания в архив
        await self.process_update_archive(actual_dates)

        async with aiofiles.open(f"{WORKSPACE}current_date.txt", "r") as file:
            content = await file.read()
            current_dates = list(set(content.splitlines()))

        print(f"{actual_dates} - now + today")
        print(f"{actual_current_dates} - sended actual")
        print(f"{current_dates} - all sended")

        # Фильтрация новых дат, которые не были отправлены
        new_dates: list[str] = [date for date in actual_dates if date not in actual_current_dates]

        if new_dates:
            print(f"\n📆 Расписание появилось! {new_dates}")
            await self.handle_new_schedules(new_dates, actual_dates)

            async with aiofiles.open(f"{WORKSPACE}current_date.txt", "r") as file:
                content = await file.read()
                current_dates = list(set(content.splitlines()))

        # updated_current_dates = list(
        #    set(current_dates) & set(actual_dates)
        # )  # Только общие даты

        # groups = await self.db_users.get_groups()

        # for group in groups:
        #    for date in updated_current_dates:
        #        schedule = await self.schedule_service.get_schedule(group, date)

        #        await self.check_schedule_change(group, date, schedule) # type: ignore

    async def handle_new_schedules(self, new_dates: list[str], actual_dates: list[str]) -> None:
        """A method for processing the schedule that appears"""
        async for session in self.db_manager.get_session():  # type: ignore
            groups = await UserRepository.get_all_groups(session)

        with open(f"{WORKSPACE}current_date.txt", "a") as file:
            file.write("\n")
            file.write("\n".join(actual_dates))

        start = time.perf_counter()
        await self.send_schedule_mentors(new_dates)
        await self.send_schedule_chats(new_dates)
        await self.send_schedule_groups(new_dates, groups)
        end = time.perf_counter()

        total_seconds = end - start
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        print("\nРасписание отправлено ✅")
        print(f"Затраченное время: {minutes}m {seconds:2f}s ({total_seconds})s")

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
                await print_sent(user_id)
                return True

            except TelegramRetryAfter as e:
                wait = float(e.retry_after) + 1.0 + random.random()
                attempt += 1

                print(f"Error RetryAfter - {wait}")
                await asyncio.sleep(wait)

            except Exception:
                attempt += 1
                print(f"\t\t🟥 attempt({attempt}) - Ошибка при отправке {user_id}")

    async def get_all_schedule(self, dates: list[str]) -> dict[str, list[list]]:
        """A method for getting a schedule for each group"""
        async for session in self.db_manager.get_session():  # type: ignore
            groups = await UserRepository.get_all_groups(session)

        coroutines = [self.schedule_service.get_schedule(group, date) for date in dates for group in groups]

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
            async for session in self.db_manager.get_session():  # type: ignore
                users_id: list[int] = await UserRepository.get_users_by_group_and_theme(session, group, theme)

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

            tasks_create_photo.append(
                ImageCreator().create_schedule_image(
                    data=schedule,
                    date=date,
                    number_rows=len(schedule) + 1,
                    filename=filename,
                    group=group,
                    theme=theme,
                )
            )

        await asyncio.gather(*tasks_create_photo)

    @staticmethod
    async def _open_photos_schedule(themes_users: dict[str, list[int]], group: str) -> dict[str, BufferedInputFile]:
        """Method for async opening of schedule photos"""
        open_photos = dict()
        for theme in themes_users:
            filename = f"{group}_{theme}"
            async with aiofiles.open(f"{WORKSPACE}{filename}.jpeg", "rb") as f:
                photo_data = await f.read()

            photo = BufferedInputFile(photo_data, filename=f"{WORKSPACE}{filename}.jpeg")
            open_photos[theme] = photo

            del photo_data

        return open_photos

    @staticmethod
    async def _get_user_chunks(
        themes_users: dict[str, list[int]],
    ) -> dict[str, list[list[int]]]:
        """A method for splitting users into chunks"""
        user_chunks_dict = dict()

        for theme, users_id in themes_users.items():
            chunk_size = 10
            user_chunks = [users_id[i : i + chunk_size] for i in range(0, len(users_id), chunk_size)]

            user_chunks_dict[theme] = user_chunks

        return user_chunks_dict

    async def _send_no_schedule_message(self, users: list[int], group: str, date: str):
        """A method for sending a message about the absence of a schedule"""
        attempt = 0
        for user_id in users:
            async with self.limiter:
                while attempt <= 3:
                    try:
                        day = day_week_by_date(date)
                        print(f"\t\t{no_schedule_text.format(group=group, date=date, day=day)}")
                        await self.bot.send_message(
                            user_id,
                            no_schedule_text.format(group=group, date=date, day=day),
                            parse_mode="HTML",
                            disable_notification=True,
                        )
                        break

                    except TelegramRetryAfter as e:
                        wait = float(e.retry_after) + 1.0 + random.random()
                        attempt += 1

                        print(f"Error RetryAfter - {wait}")
                        await asyncio.sleep(wait)

                    except Exception:
                        attempt += 1
                        print(f"\t\t🟥 attempt({attempt}) - Ошибка при отправке {user_id} - {group}")

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

                for task in tasks:
                    async with self.limiter:
                        await asyncio.create_task(task)

                del tasks
                await asyncio.sleep(0.001)

    async def send_schedule_groups(
        self, new_dates: list[str], groups: list[str], updated_schedule: bool = False
    ) -> None:
        """The method for sending the schedule"""
        try:
            for group in groups:
                async for session in self.db_manager.get_session():  # type: ignore
                    users: list[int] = await UserRepository.get_users_by_group(session, group)

                for date in new_dates:
                    async for session in self.db_manager.get_session():  # type: ignore
                        schedule = await ScheduleArchiveRepository.get_student_schedule(session, date, group)

                    print(f"date: {date}")
                    print(f"group: {group}")
                    print(f"users: {users}")
                    print(f"schedule: {schedule}")

                    if not schedule:
                        await self._send_no_schedule_message(users, group, date)
                        continue

                    themes_users = await self._get_themes_users(group)
                    await self._create_photos_schedule(themes_users, schedule, date, group)  # type: ignore

                    open_photos = await self._open_photos_schedule(themes_users, group)

                    user_chunks_dict: dict[str, list[list[int]]] = await self._get_user_chunks(themes_users)

                    await self._send_schedule(user_chunks_dict, open_photos, updated_schedule)

                    for theme in themes_users:
                        filename = f"{group}_{theme}.jpeg"
                        (os.remove(f"{WORKSPACE}{filename}") if os.path.exists(f"{WORKSPACE}{filename}") else False)

                    del themes_users, open_photos, user_chunks_dict
                    gc.collect()

                gc.collect()

        except Exception as e:
            print(format_error_message(self.send_schedule_groups.__name__, e))

    async def send_schedule_mentors(
        self,
        new_dates: list[str],
    ) -> None:
        """The method for sending the schedule for mentors"""
        try:
            async for session in self.db_manager.get_session():  # type: ignore
                mentors: list = await UserRepository.get_all_mentors(session)

            for mentor in mentors:
                mentor_id = mentor[0]  # type: ignore
                mentor_name = mentor[1]  # type: ignore

                for date in new_dates:
                    async for session in self.db_manager.get_session():  # type: ignore
                        schedule = await ScheduleArchiveRepository.get_mentor_schedule(session, date, mentor_name)

                    if not any(schedule):
                        day = day_week_by_date(date)
                        print(no_schedule_mentor_text.format(mentor_name=mentor_name, date=date, day=day))
                        await self.bot.send_message(
                            mentor_id,
                            no_schedule_mentor_text.format(mentor_name=mentor_name, date=date, day=day),
                            parse_mode="HTML",
                        )

                        continue

                    async for session in self.db_manager.get_session():  # type: ignore
                        user_theme = await UserRepository.get_user_theme(session, mentor_id)

                    await ImageCreator().create_schedule_image(
                        data=schedule,
                        date=date,
                        number_rows=len(schedule) + 1,
                        filename=f"{mentor_id}{mentor_name}",
                        group=mentor_name,
                        theme=user_theme,
                    )

                    photo = FSInputFile(path=f"{WORKSPACE}{mentor_id}{mentor_name}.jpeg")

                    await self.safe_send_photo(mentor_id, photo, updated=False)

                    (
                        os.remove(f"{WORKSPACE}{mentor_id}{mentor_name}.jpeg")
                        if os.path.exists(f"{WORKSPACE}{mentor_id}{mentor_name}.jpeg")
                        else False
                    )

        except Exception as e:
            print(format_error_message(self.send_schedule_mentors.__name__, e))

    async def send_schedule_chats(self, new_dates: list[str], updated_schedule: bool = False) -> None:
        """The method for sending the schedule"""
        try:
            async for session in self.db_manager.get_session():  # type: ignore
                chats = await ChatRepository.get_all_chats_with_subscriptions(session)

            for chat in chats:
                chat_id = chat["chat_id"]
                group = chat["subscribed_to_group"]
                mentor = chat["subscribed_to_mentor"]

                for date in new_dates:
                    async for session in self.db_manager.get_session():  # type: ignore
                        schedule_group = await ScheduleArchiveRepository.get_student_schedule(session, date, group)
                        schedule_mentor = await ScheduleArchiveRepository.get_mentor_schedule(session, date, mentor)

                    if not any(schedule_group):
                        day = day_week_by_date(date)
                        print(no_schedule_text.format(group=group, date=date, day=day))
                        await self.bot.send_message(
                            chat_id,
                            no_schedule_text.format(group=group, date=date, day=day),
                            parse_mode="HTML",
                        )
                    else:
                        await ImageCreator().create_schedule_image(
                            data=schedule_group,
                            date=date,
                            number_rows=len(schedule_group) + 1,
                            filename=f"{chat_id}{group}",
                            group=group,
                            theme="Classic",
                        )

                        photo = FSInputFile(path=f"{WORKSPACE}{chat_id}{group}.jpeg")

                        await self.safe_send_photo(chat_id, photo, updated=False)

                        (
                            os.remove(f"{WORKSPACE}{chat_id}{group}.jpeg")
                            if os.path.exists(f"{WORKSPACE}{chat_id}{group}.jpeg")
                            else False
                        )

                        del photo
                        gc.collect()

                    if not any(schedule_mentor):
                        day = day_week_by_date(date)
                        print(no_schedule_mentor_text.format(mentor_name=mentor, date=date, day=day))
                        await self.bot.send_message(
                            chat_id,
                            no_schedule_mentor_text.format(mentor_name=mentor, date=date, day=day),
                            parse_mode="HTML",
                        )
                    else:
                        await ImageCreator().create_schedule_image(
                            data=schedule_mentor,
                            date=date,
                            number_rows=len(schedule_mentor) + 1,
                            filename=f"{chat_id}{mentor}",
                            group=mentor,
                            theme="Classic",
                        )

                        photo = FSInputFile(path=f"{WORKSPACE}{chat_id}{mentor}.jpeg")

                        await self.safe_send_photo(chat_id, photo, updated=False)

                        (
                            os.remove(f"{WORKSPACE}{chat_id}{mentor}.jpeg")
                            if os.path.exists(f"{WORKSPACE}{chat_id}{mentor}.jpeg")
                            else False
                        )

                        del photo
                        gc.collect()

                gc.collect()

        except Exception as e:
            print(format_error_message(self.send_schedule_groups.__name__, e))
