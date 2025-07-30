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
    def __init__(self, bot, db_users, db_hashes):
        self.bot = bot
        self.db_users = db_users
        self.db_hashes = db_hashes
        self.schedule_service = ScheduleService()

    async def get_current_hour(self) -> int:
        return datetime.now().hour  # type: ignore

    # ---NOT-CHECHED---#
    async def check_schedule(self) -> None:
        print("Проверка актуального расписания запущена ✅ 🔄")
        count = 1
        try:
            while True:
                hour = await self.get_current_hour()

                if hour >= 22 or hour <= 7:
                    print(f"Остановка проверки расписания на 1ч (22:00 - 8:00) 🟥")
                    print(f"Текущее время: {hour}ч")
                    self.db_hashes.cleanup_old_hashes()
                    await asyncio.sleep(3600)
                    continue

                actual_dates = await self.schedule_service.get_dates_schedule()

                with open(f"{WORKSPACE}current_date.txt", "r") as file:
                    current_dates = file.read().splitlines()

                print(f"{current_dates} - sended")
                print(f"{actual_dates} - actual")

                # Фильтрация новых дат, которые не были отправлены
                not_sended_dates: list[str] = [
                    date for date in actual_dates if date not in current_dates
                ]

                if not_sended_dates:
                    print(f"\n📆 Расписание появилось! {not_sended_dates}")
                    start_send_time = time.time()

                    print("Получение расписания для каждой группы... ⏳")
                    groups_schedule = await self.get_all_schedule(not_sended_dates)

                    print("Расписание получено! ✅")

                    await self.check_schedule_change(groups_schedule)

                    await self.send_schedule(groups_schedule)

                    with open(f"{WORKSPACE}current_date.txt", "w") as file:
                        file.write("\n".join(actual_dates))

                    end_send_time = time.time()
                    print("\nРасписание отправлено ✅")
                    print(f"Затраченное время: {end_send_time - start_send_time}")

                updated_current_dates = list(
                    set(current_dates) & set(actual_dates)
                )  # Только общие даты

                groups_schedule = await self.get_all_schedule(updated_current_dates)
                await self.check_schedule_change(groups_schedule)

                print(f"Ожидание расписания... ⏳ I-{count}")
                count += 1
                await asyncio.sleep(60)
                continue

        except Exception as e:
            print(format_error_message(self.check_schedule.__name__, e))
            await asyncio.sleep(3)

    async def check_schedule_change(
        self, groups_schedule: dict[str, list[list]]
    ) -> None:
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
        groups = self.db_users.get_groups()

        coroutines = [ self.schedule_service.get_schedule(group, date) for group in groups for date in dates ]

        keys = [f"{group} {date}" for group in groups for date in dates]

        results = await asyncio.gather(*coroutines)
        groups_schedule: dict[str, list[list]] = dict(zip(keys, results))

        return groups_schedule

    # ---NOT-CHECHED---#
    async def send_schedule(
        self,
        groups_schedule: dict[str, list[list]],
        filename: str = "schedule",
        updated_schedule: bool = False,
    ) -> None:
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

                print(f"themes_users: {themes_users}")

                if not any(schedule):
                    for user_id in users:
                        try:
                            print(
                                f"\t\t{no_schedule_for_date.format(group=group, date=date)}"
                            )
                            await self.bot.send_message(
                                user_id,
                                no_schedule_for_date.format(group=group, date=date),
                                parse_mode="HTML",
                            )
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            print(
                                f"\t\t🟥 Ошибка при отправке сообщения пользователю {user_id} - {group}\n"
                            )

                    await asyncio.sleep(3)
                    continue

                tasks_create_photo = []
                for theme in themes_users:
                    image_creator = ImageCreator()
                    tasks_create_photo.append(
                        await image_creator.create_schedule_image(
                            data=data,
                            date=date,
                            number_rows=len(data) + 1,
                            filename=f"{user_id}{filename}",
                            theme=theme,
                        )
                    )

                await asyncio.gather(*tasks_create_photo)

                open_photos = dict()
                for theme in themes_users:
                    async with aiofiles.open(
                        f"{WORKSPACE}{filename}_{theme}.jpeg", "rb"
                    ) as f:
                        photo_data = await f.read()

                    photo = BufferedInputFile(
                        photo_data, filename=f"{WORKSPACE}{filename}_{theme}.jpeg"
                    )
                    open_photos[theme] = photo

                for theme, users_id in themes_users.items():
                    chunk_size = 10
                    user_chunks = [
                        users_id[i : i + chunk_size]
                        for i in range(0, len(users_id), chunk_size)
                    ]

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

                await asyncio.sleep(3)

        except Exception as e:
            print(format_error_message(self.send_schedule.__name__, e))
