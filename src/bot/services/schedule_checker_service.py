import asyncio
import os
import time
from datetime import datetime

import aiofiles
from aiogram.types import BufferedInputFile
from config import themes_names
from config.paths import WORKSPACE
from phrases import no_schedule_for_date

from services.image_service import ImageCreator
from services.schedule_service import ScheduleService
from utils.formatters import format_error_message
from utils.hash import generate_hash
from utils.log import print_sent


class ScheduleChecker:
    """Класс для отслеживания появления и изменения расписания"""

    SLEEP_NIGHT = 3600
    SLEEP_DAY = 60
    NIGHT_HOURS = (22, 23, 0, 1, 2, 3, 4, 5, 6, 7)

    def __init__(self, bot, db_users, db_hashes):
        """Инициализация необходимых зависимостей"""
        self.bot = bot
        self.db_users = db_users
        self.db_hashes = db_hashes
        self.schedule_service = ScheduleService()

    async def is_night_time(self) -> bool:
        """Метод для получения текущего часа"""
        return datetime.now().hour in self.NIGHT_HOURS

    async def run_schedule_check(self) -> None:
        """Метод для запуска отслеживания появления и изменения расписания"""
        print("Проверка расписания запущена ✅ 🔄")
        iteration = 1
        try:
            while True:
                if await self.is_night_time():
                    print(f"🌙 Остановка проверки на 1ч (ночное время)")
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
        """Метод для обработки расписания"""
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

    async def handle_new_schedules(self, new_dates: list[str], actual_dates: list[str]) -> None:
        """Метод для обработки появившегося расписания"""
        groups_schedule = await self.get_all_schedule(new_dates) # Получение расписания для каждой группы
        await self.check_schedule_change(groups_schedule) # Добавление хешей расписания в базу данных

        start_send_time = time.time()

        await self.send_schedule(groups_schedule) # Начало рассылки расписания

        end_send_time = time.time()

        with open(f"{WORKSPACE}current_date.txt", "w") as file:
            file.write("\n".join(actual_dates))

        print("\nРасписание отправлено ✅")
        print(f"Затраченное время: {end_send_time - start_send_time}")

    async def check_schedule_change(
        self, groups_schedule: dict[str, list[list]]
    ) -> None:
        """Метод для отслеживания изменения расписания"""
        try:
            for group_date, schedule in groups_schedule.items():
                data = group_date.split(" ")
                group = data[0]
                date = data[1]

                hash_value: str = await generate_hash(schedule)

                if self.db_hashes.check_hash_change(group, date, hash_value) == True:
                    print(f"Расписание у группы {group} - {date} изменилось")
                    await self.send_schedule({f"{group} {date}": schedule}, group, True)  # type: ignore

                    for theme in themes_names:
                        if os.path.exists(f"{WORKSPACE}{group}_{theme}.jpeg"):
                            os.remove(f"{WORKSPACE}{group}_{theme}.jpeg")

                elif self.db_hashes.check_hash_change(group, date, hash_value) == False:
                    continue
        except Exception as e:
            print(format_error_message(self.check_schedule_change.__name__, e))
            await asyncio.sleep(3)

    async def safe_send_photo(self, user_id: int, photo, updated: bool):
        """Метод для отправки фото расписания"""
        try:
            if updated:
                await self.bot.send_photo(
                    user_id, photo=photo, caption="🆕 Расписание изменилось!"
                )
                return

            await self.bot.send_photo(user_id, photo)
        except Exception as e:
            print(f"Ошибка send_photo для {user_id}")

    async def get_all_schedule(self, dates: list[str]) -> dict[str, list[list]]:
        """Метод для получения расписания для каждой группы"""
        groups = self.db_users.get_groups()

        coroutines = [
            self.schedule_service.get_schedule(group, date)
            for group in groups
            for date in dates
        ]

        keys = [f"{group} {date}" for group in groups for date in dates]

        results = await asyncio.gather(*coroutines)
        groups_schedule: dict[str, list[list]] = dict(zip(keys, results))

        return groups_schedule

    async def _get_themes_users(self, group: str) -> dict[str, list[int]]:
        """Метод для получения пользователей которые используют определенную тему расписания"""
        themes_users: dict = {}
        users_id: list[int] = []

        for theme in themes_names:
            users_id: list[int] = self.db_users.get_users_by_theme(group, theme)

            if any(users_id):
                print(f"\t✅ 🌌 Есть пользователи с темой {theme}")
                themes_users[theme] = users_id
            else:
                print(f"\t❌ 🌌 Нет пользователей с темой {theme}")
                continue

        return themes_users

    @staticmethod
    async def _create_photos_schedule(
        themes_users: dict[str, list[int]],
        schedule: list,
        date: str,
        filename: str
    ) -> None:
        """Метод для асинхронного создания фото рассписания"""
        tasks_create_photo = []
        for theme in themes_users:
            image_creator = ImageCreator()
            tasks_create_photo.append(
                await image_creator.create_schedule_image(
                    data=schedule,
                    date=date,
                    number_rows=len(schedule) + 1,
                    filename=f"{filename}_{theme}",
                    theme=theme,
                )
            )

        await asyncio.gather(*tasks_create_photo)

    @staticmethod
    async def _open_photos_schedule(
        themes_users: dict[str, list[int]], filename: str
    ) -> dict[str, BufferedInputFile]:
        """Метод для асинхронного открытия фото расписания"""
        open_photos = dict()
        for theme in themes_users:
            async with aiofiles.open(f"{WORKSPACE}{filename}_{theme}.jpeg", "rb") as f:
                photo_data = await f.read()

            photo = BufferedInputFile(
                photo_data, filename=f"{WORKSPACE}{filename}_{theme}.jpeg"
            )
            open_photos[theme] = photo

        return open_photos

    @staticmethod
    async def _get_user_chunks(
        themes_users: dict[str, list[int]]
    ) -> dict[str, list[list[int]]]:
        """Метод для разбития пользователей на чанки по 10 человек в чанк"""
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
        """Метод для отправки сообщения об отсутствии расписания"""
        for user_id in users:
            try:
                print(f"\t\t{no_schedule_for_date.format(group=group, date=date)}")
                await self.bot.send_message(
                    user_id,
                    no_schedule_for_date.format(group=group, date=date),
                    parse_mode="HTML",
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"\t\t🟥 Ошибка при отправке сообщения пользователю {user_id} - {group}\n")

        await asyncio.sleep(3)

    async def _send_schedule(
        self,
        user_chunks_dict: dict[str, list[list[int]]],
        open_photos: dict[str, BufferedInputFile],
        updated_schedule: bool,
    ) -> None:
        """Метод для отправки фото рассписания по чанкам"""
        for theme, user_chunks in user_chunks_dict.items():
            photo = open_photos[theme]

            for chunk in user_chunks:
                tasks = []
                for user_id in chunk:
                    tasks.append(print_sent(user_id))

                    if updated_schedule:
                        tasks.append(self.safe_send_photo(user_id, photo, True))
                        continue
                    tasks.append(self.safe_send_photo(user_id, photo, False))

                await asyncio.gather(*tasks)
                await asyncio.sleep(3)


    async def send_schedule(
        self,
        groups_schedule: dict[str, list[list]],
        filename: str = "schedule",
        updated_schedule: bool = False,
    ) -> None:
        """Метод для отправки расписания"""
        try:
            # | groups_schedule: { [group, date]: list[list] }

            for group_date, schedule in groups_schedule.items():
                data = group_date.split(" ")
                group = data[0]
                date = data[1]

                users: list[int] = self.db_users.get_users_by_group(group)

                print(f"group: {group}")
                print(f"date: {date}")
                print(f"users: {users}")

                themes_users = await self._get_themes_users(group)

                if not any(schedule):
                    await self._send_no_schedule_message(users, group, date)
                    continue

                await self._create_photos_schedule(themes_users, schedule, date, filename)

                open_photos = await self._open_photos_schedule(themes_users, group)

                user_chunks_dict: dict[str, list[list[int]]] = (
                    await self._get_user_chunks(themes_users)
                )

                await self._send_schedule(
                    user_chunks_dict, open_photos, updated_schedule
                )

                await asyncio.sleep(3)
        except Exception as e:
            print(format_error_message(self.send_schedule.__name__, e))
