"""Schedule checker service.

This module contains ScheduleChecker class which periodically polls the schedule
source, archives schedules for groups and mentors, and sends notifications/images
to users/chats.

Important:
    The sending logic in this file is sensitive. Even seemingly redundant steps
    can be relied upon by the runtime behavior (rate limits, intermediate files,
    and ordering). Refactors must preserve input/output behavior.
"""

import asyncio
import gc
from hmac import new
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List

import aiofiles
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import BufferedInputFile, FSInputFile
from aiolimiter import AsyncLimiter

from config.themes import THEMES_NAMES
from config.paths import WORKSPACE
from phrases import no_schedule_mentor_text, no_schedule_text
from services.image_service import ImageCreator
from services.schedule_service import ScheduleService
from utils.formatters import format_error_message
from utils.hash import generate_hash
from utils.log import print_sent
from utils.utils import day_week_by_date

from services.database import (
    ChatRepository,
    ScheduleArchiveRepository,
    ScheduleHashRepository,
    UserRepository,
)


class ScheduleChecker:
    """Track schedule appearances and send schedule to subscribers.

    The checker runs in a loop:
    1. During night hours it pauses checks, performs DB cleanup, and sleeps.
    2. During day hours it fetches current dates, updates the archive, and if new
       dates appear it triggers the broadcast pipeline.

    Attributes:
        bot: Aiogram bot instance used for message/photo sending.
        db_manager: Database manager that yields sessions via get_session.
        schedule_service: ScheduleService for fetching dates/schedules.
        limiter: Rate limiter that throttles Telegram API calls.
    """

    SLEEP_NIGHT = 3600
    SLEEP_DAY = 180
    NIGHT_HOURS = (22, 23, 0, 1, 2, 3, 4, 5, 6, 7)

    def __init__(self, bot: Any, db_manager: Any) -> None:
        """Create a new schedule checker.

        Args:
            bot: Aiogram bot instance.
            db_manager: DB manager that provides async generator get_session.
        """
        self.bot = bot
        self.db_manager = db_manager
        self.schedule_service = ScheduleService()
        self.limiter = AsyncLimiter(15, 7)

    async def _with_session(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a DB operation within a single acquired session.

        This helper reduces repeated session acquisition inside tight loops.

        Args:
            fn: Callable that accepts session as the first argument.
            *args: Positional args forwarded to fn.
            **kwargs: Keyword args forwarded to fn.

        Returns:
            The return value of fn.
        """
        async for session in self.db_manager.get_session():  # type: ignore
            return await fn(session, *args, **kwargs)

    @classmethod
    async def is_night_time(cls) -> bool:
        """Check whether current local time is considered night hours."""
        return datetime.now().hour in cls.NIGHT_HOURS

    async def run_schedule_check(self) -> None:
        """Run the infinite schedule polling loop."""
        iteration = 1
        try:
            while True:
                if await self.is_night_time():
                    print(f"🌙 Остановка проверки на 1ч (ночное время)")
                    print(f"Текущий час: {datetime.now().hour}")

                    await self._with_session(ScheduleHashRepository.cleanup_old_hashes)

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

    async def process_update_archive(self, dates: List[str]) -> None:
        """Update schedule archive for all groups and mentors for provided dates.

        Args:
            dates: Date strings to archive (DD.MM.YYYY).
        """
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

                await self._with_session(
                    ScheduleArchiveRepository.update_student_schedule,
                    date,
                    group,
                    schedule,
                    hash_value,
                )

            for mentor in mentors:
                schedule = await self.schedule_service.get_mentors_schedule(mentor, date)
                if not schedule:
                    continue
                hash_value: str = await generate_hash(schedule)

                await self._with_session(
                    ScheduleArchiveRepository.update_mentor_schedule,
                    date,
                    mentor,
                    schedule,
                    hash_value,
                )

    async def process_hash_updates(self, dates: List[str]) -> None:
        """Update hashes for current dates to track schedule changes.

        Args:
            dates: Current date strings to update hashes for.
        """
        async with aiofiles.open(f"{WORKSPACE}all_groups.txt", "r") as file:
            content = await file.read()
            groups = list(set(content.splitlines()))

        async with aiofiles.open(f"{WORKSPACE}all_mentors.txt", "r") as file:
            content = await file.read()
            mentors = list(set(content.splitlines()))

        print("Начало обновления хешей")

        for date in dates:
            for group in groups:
                schedule = await self.schedule_service.get_schedule(group, date)
                if not schedule:
                    continue
                hash_value: str = await generate_hash(schedule)

                hash_changed = await self._with_session(
                    ScheduleHashRepository.check_and_update_hash,
                    group,
                    date,
                    hash_value,
                )
                if hash_changed:
                    print(f"Хэш изменен для группы {group} на {date}")
                else:
                    print(f"Хэш без изменений для группы {group} на {date}")

            for mentor in mentors:
                schedule = await self.schedule_service.get_mentors_schedule(mentor, date)
                if not schedule:
                    continue
                hash_value: str = await generate_hash(schedule)

                hash_changed = await self._with_session(
                    ScheduleHashRepository.check_and_update_hash,
                    mentor,
                    date,
                    hash_value,
                )
                if hash_changed:
                    print(f"Хэш изменен для ментора {mentor} на {date}")
                else:
                    print(f"Хэш без изменений для ментора {mentor} на {date}")

    async def process_schedule_updates(self) -> None:
        """Fetch dates, update hashes, and trigger broadcasts for new dates."""
        actual_dates = await self.schedule_service.get_dates_schedule()
        actual_current_dates = await self.schedule_service.get_actual_current_dates()

        await self.process_update_archive(actual_dates)

        async with aiofiles.open(f"{WORKSPACE}current_date.txt", "r") as file:
            content = await file.read()
            current_dates = list(set(content.splitlines()))

        print(f"{actual_dates} - now + today")
        print(f"{actual_current_dates} - sended actual")
        print(f"{current_dates} - all sended")

        new_dates: List[str] = [date for date in actual_dates if date not in actual_current_dates]

        if new_dates:
            print(f"\n📆 Расписание появилось! {new_dates}")
            await self.handle_new_schedules(new_dates, actual_dates)

    async def handle_new_schedules(self, new_dates: List[str], actual_dates: List[str]) -> None:
        """Handle a newly appeared schedule dates set.

        Args:
            new_dates: Dates that were not previously sent.
            actual_dates: Full list of currently available dates.
        """
        groups = await self._with_session(UserRepository.get_all_groups)

        try:
            with open(f"{WORKSPACE}current_date.txt", "a", encoding="utf-8") as file:
                file.write("\n")
                file.write("\n".join(actual_dates))
        except OSError as e:
            print(format_error_message(self.handle_new_schedules.__name__, e))

        start = time.perf_counter()
        await self.send_schedule_mentors(new_dates)
        await self.send_schedule_chats(new_dates)
        await self.send_schedule_groups(new_dates, groups)
        end = time.perf_counter()

        total_seconds = end - start
        minutes = total_seconds // 60
        seconds = total_seconds % 60

        print("\nРасписание отправлено ✅")
        print(f"Затраченное время: {minutes}m {seconds:.2f}s ({total_seconds}s)")

    async def safe_send_photo(self, user_id: int, photo: Any, updated: bool) -> bool | None:
        """Send a photo with retries and RetryAfter handling.

        Args:
            user_id: Telegram user/chat id.
            photo: Photo input file (BufferedInputFile/FSInputFile).
            updated: If True, adds an "updated schedule" caption.

        Returns:
            True if photo was sent successfully, otherwise None.
        """
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

        return None

    async def get_all_schedule(self, dates: List[str]) -> Dict[str, List[List[Any]]]:
        """Get schedule for each group/date combination.

        This is a utility method. It preserves the original sequential behavior
        (to avoid changing load patterns on the remote schedule server).

        Args:
            dates: List of dates to fetch.

        Returns:
            Mapping "{group} {date}" to parsed schedule tables.
        """
        groups = await self._with_session(UserRepository.get_all_groups)

        groups_schedule: Dict[str, List[List[Any]]] = {}
        for group in groups:
            for date in dates:
                groups_schedule[f"{group} {date}"] = await self.schedule_service.get_schedule(group, date)

        return groups_schedule

    async def _get_themes_users(self, group: str) -> Dict[str, List[int]]:
        """Get users split by theme for a group.

        Args:
            group: Group code.

        Returns:
            Mapping theme name to list of user ids.
        """
        themes_users: Dict[str, List[int]] = {}

        for theme in THEMES_NAMES:
            users_id = await self._with_session(UserRepository.get_users_by_group_and_theme, group, theme)
            if users_id:
                themes_users[theme] = users_id

        return themes_users

    @staticmethod
    async def _create_photos_schedule(
        themes_users: Dict[str, List[int]], schedule: List[Any], date: str, group: str
    ) -> None:
        """Create schedule images for each theme.

        Args:
            themes_users: Mapping of themes to users (themes determine what to render).
            schedule: Parsed schedule table.
            date: Schedule date.
            group: Group code.
        """
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
    async def _open_photos_schedule(themes_users: Dict[str, List[int]], group: str) -> Dict[str, BufferedInputFile]:
        """Load generated images into memory as BufferedInputFile.

        Note:
            BufferedInputFile keeps the full bytes in memory. The caller should
            drop references as soon as sending finishes.

        Args:
            themes_users: Themes for which images exist.
            group: Group code used in filenames.

        Returns:
            Mapping theme to BufferedInputFile.
        """
        open_photos = {}
        for theme in themes_users:
            filename = f"{group}_{theme}"
            async with aiofiles.open(f"{WORKSPACE}{filename}.jpeg", "rb") as f:
                photo_data = await f.read()

            photo = BufferedInputFile(photo_data, filename=f"{WORKSPACE}{filename}.jpeg")
            open_photos[theme] = photo

            del photo_data

        return open_photos

    @staticmethod
    async def _get_user_chunks(themes_users: Dict[str, List[int]]) -> Dict[str, List[List[int]]]:
        """Split user ids into small chunks to limit concurrent sends."""
        user_chunks_dict = {}

        for theme, users_id in themes_users.items():
            chunk_size = 10
            user_chunks = [users_id[i : i + chunk_size] for i in range(0, len(users_id), chunk_size)]

            user_chunks_dict[theme] = user_chunks

        return user_chunks_dict

    async def _send_no_schedule_message(self, users: List[int], group: str, date: str) -> None:
        """Send a "no schedule" message to a list of users.

        Args:
            users: List of user ids.
            group: Group code.
            date: Date string.
        """
        for user_id in users:
            async with self.limiter:
                attempt = 0
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
        user_chunks_dict: Dict[str, List[List[int]]],
        open_photos: Dict[str, BufferedInputFile],
        updated_schedule: bool,
    ) -> None:
        """Send schedule photos to users by chunks, respecting the limiter."""
        for theme, user_chunks in user_chunks_dict.items():
            photo = open_photos[theme]

            for chunk in user_chunks:
                for user_id in chunk:
                    async with self.limiter:
                        await self.safe_send_photo(user_id, photo, updated_schedule)
                await asyncio.sleep(0.001)

    async def send_schedule_groups(
        self, new_dates: List[str], groups: List[str], updated_schedule: bool = False
    ) -> None:
        """Send group schedules to all users subscribed to given groups."""
        try:
            for group in groups:
                users: List[int] = await self._with_session(UserRepository.get_users_by_group, group)

                for date in new_dates:
                    schedule = await self._with_session(ScheduleArchiveRepository.get_student_schedule, date, group)

                    print(f"date: {date}")
                    print(f"group: {group}")
                    print(f"users: {users}")
                    print(f"schedule: {schedule}")

                    if not schedule:
                        await self._send_no_schedule_message(users, group, date)
                        continue

                    themes_users = await self._get_themes_users(group)
                    try:
                        await self._create_photos_schedule(themes_users, schedule, date, group)  # type: ignore
                        open_photos = await self._open_photos_schedule(themes_users, group)
                        user_chunks_dict: Dict[str, List[List[int]]] = await self._get_user_chunks(themes_users)
                        await self._send_schedule(user_chunks_dict, open_photos, updated_schedule)
                    finally:
                        for theme in themes_users:
                            filename = f"{group}_{theme}.jpeg"
                            try:
                                os.remove(f"{WORKSPACE}{filename}")
                            except FileNotFoundError:
                                pass
                            except OSError as e:
                                print(format_error_message(self.send_schedule_groups.__name__, e))

                        try:
                            del open_photos
                            del user_chunks_dict
                        except UnboundLocalError:
                            pass
                        del themes_users
                        gc.collect()

                gc.collect()

        except Exception as e:
            print(format_error_message(self.send_schedule_groups.__name__, e))

    async def send_schedule_mentors(self, new_dates: List[str]) -> None:
        """Send mentors schedules to mentors (users stored as mentors)."""
        try:
            mentors: List = await self._with_session(UserRepository.get_all_mentors)

            for mentor in mentors:
                mentor_id = mentor[0]  # type: ignore
                mentor_name = mentor[1]  # type: ignore

                for date in new_dates:
                    schedule = await self._with_session(ScheduleArchiveRepository.get_mentor_schedule, date, mentor_name)

                    if not any(schedule):
                        day = day_week_by_date(date)
                        print(no_schedule_mentor_text.format(mentor_name=mentor_name, date=date, day=day))
                        await self.bot.send_message(
                            mentor_id,
                            no_schedule_mentor_text.format(mentor_name=mentor_name, date=date, day=day),
                            parse_mode="HTML",
                        )

                        continue

                    user_theme = await self._with_session(UserRepository.get_user_theme, mentor_id)

                    await ImageCreator().create_schedule_image(
                        data=schedule,
                        date=date,
                        number_rows=len(schedule) + 1,
                        filename=f"{mentor_id}{mentor_name}",
                        group=mentor_name,
                        theme=user_theme,
                    )

                    photo_path = f"{WORKSPACE}{mentor_id}{mentor_name}.jpeg"
                    try:
                        photo = FSInputFile(path=photo_path)
                        await self.safe_send_photo(mentor_id, photo, updated=False)
                    finally:
                        try:
                            os.remove(photo_path)
                        except FileNotFoundError:
                            pass
                        except OSError as e:
                            print(format_error_message(self.send_schedule_mentors.__name__, e))

        except Exception as e:
            print(format_error_message(self.send_schedule_mentors.__name__, e))

    async def send_schedule_chats(self, new_dates: List[str], updated_schedule: bool = False) -> None:
        """Send schedules to chats that subscribed to a group and/or a mentor."""
        try:
            chats = await self._with_session(ChatRepository.get_all_chats_with_subscriptions)

            for chat in chats:
                chat_id = chat["chat_id"]
                group = chat["subscribed_to_group"]
                mentor = chat["subscribed_to_mentor"]

                for date in new_dates:
                    schedule_group = (
                        await self._with_session(ScheduleArchiveRepository.get_student_schedule, date, group)
                        if group
                        else []
                    )
                    schedule_mentor = (
                        await self._with_session(ScheduleArchiveRepository.get_mentor_schedule, date, mentor)
                        if mentor
                        else []
                    )

                    if not group or not any(schedule_group):
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

                        photo_path = f"{WORKSPACE}{chat_id}{group}.jpeg"
                        try:
                            photo = FSInputFile(path=photo_path)
                            await self.safe_send_photo(chat_id, photo, updated=False)
                        finally:
                            try:
                                os.remove(photo_path)
                            except FileNotFoundError:
                                pass
                            except OSError as e:
                                print(format_error_message(self.send_schedule_chats.__name__, e))

                        del photo
                        gc.collect()

                    if not mentor or not any(schedule_mentor):
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

                        photo_path = f"{WORKSPACE}{chat_id}{mentor}.jpeg"
                        try:
                            photo = FSInputFile(path=photo_path)
                            await self.safe_send_photo(chat_id, photo, updated=False)
                        finally:
                            try:
                                os.remove(photo_path)
                            except FileNotFoundError:
                                pass
                            except OSError as e:
                                print(format_error_message(self.send_schedule_chats.__name__, e))

                        del photo
                        gc.collect()

                gc.collect()

        except Exception as e:
            print(format_error_message(self.send_schedule_groups.__name__, e))
