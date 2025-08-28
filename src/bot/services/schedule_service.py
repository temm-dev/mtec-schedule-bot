import asyncio
import os
import re
from datetime import datetime

import aiohttp
from aiogram.types import FSInputFile
from config.paths import WORKSPACE
from config.requests_data import base_request_headers, request_data, requets_url
from config.themes import themes_names
from phrases import *
from utils.formatters import format_error_message
from utils.utils import day_week_by_date


class ScheduleService:
    """A class for working with a schedule"""

    @staticmethod
    async def _send_request(url: str, headers: dict, data: dict) -> str | None:
        """Method for sending a request to the server"""
        try:
            while True:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url=url,
                        headers=headers,
                        data=data,
                    ) as response:
                        text = await response.text()

                return text
        except Exception as e:
            print(f"Ошибка отправки запроса _send_request\n{e}")
            await asyncio.sleep(1)

    @staticmethod
    def _validation_arguments(group: str, date: str):
        """A method for validating arguments"""
        if not isinstance(group, str):
            raise TypeError('The "group" parameter does not equal the str data type.')

        if not isinstance(date, str):
            raise TypeError('The "date" parameter does not equal the str data type.')

    @staticmethod
    def _parse_schedule_html(html_content: str) -> list[list[str]]:
        """A method for parsing HTML schedules and returning structured data (crutch)"""
        with open(f"{WORKSPACE}schedule.html", "w") as file:
            file.write(html_content)

        os.system(f'grep "<td " {WORKSPACE}schedule.html > {WORKSPACE}schedule.txt')

        input_list = []
        with open(f"{WORKSPACE}schedule.txt", "r") as file:
            text = file.read()
            text = text.replace("        ", "")
            text = text.replace('<td class="has-text-align-center">', "")
            text = text.replace("</td>", "")
            text = text.replace('<td class="has-text-align-center text">', "")
            text = text.replace("<br>", "\n")

            input_list = text.split("\n")
            input_list = input_list[3:]

        data = []
        for i in range(0, len(input_list), 4):
            if i + 3 < len(input_list):
                pair = input_list[i] + "\nпара"
                subject = input_list[i + 1] + "\n" + input_list[i + 2]
                room = input_list[i + 3]
                data.append([pair, subject, room])

        return data

    @classmethod
    async def get_dates_schedule(cls, actual_dates: bool = True) -> list[str] | list:
        """A method for getting the available dates in the schedule"""
        try:
            response = await cls._send_request(
                requets_url, base_request_headers, request_data
            )

            if not isinstance(response, str):
                print("Response is not 'str' type - get_dates_schedule")
                return []

            date_pattern = r">(\d{1,2}\.\d{1,2}\.\d{4})<"
            dates = re.findall(date_pattern, response)

            if actual_dates:
                today = datetime.now()
                actual_dates_list = [
                    date
                    for date in dates
                    if datetime.strptime(date, "%d.%m.%Y") >= today
                ]
                return actual_dates_list

            return dates
        except Exception as e:
            print(format_error_message(cls.get_dates_schedule.__name__, e))
            return []

    @classmethod
    async def get_groups_schedule(cls) -> list[str]:
        """Method for getting available groups"""
        try:
            response = await cls._send_request(
                requets_url, base_request_headers, request_data
            )

            if not isinstance(response, str):
                print("Response is not 'str' type - get_groups_schedule")
                return []

            group_pattern = r">([A-ZА-Я]+\d{3})<"
            groups = re.findall(group_pattern, response)

            return groups
        except Exception as e:
            print(format_error_message(cls.get_groups_schedule.__name__, e))
            return []

    @classmethod
    async def get_schedule(cls, group: str, date: str) -> list[list[str]]:
        """Gets the schedule for the specified group by date"""
        cls._validation_arguments(group, date)

        request_data_schedule = {
            "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "action": "sendSchedule",
            "date": date,
            "value": group,
            "rtype": "stds",
        }

        try:
            response = await cls._send_request(
                requets_url, base_request_headers, request_data_schedule
            )

            if not isinstance(response, str):
                print("Response is not 'str' type - get_schedule")
                return []

            return cls._parse_schedule_html(response)

        except Exception as e:
            print(format_error_message(cls.get_schedule.__name__, e))
            return []

    @classmethod
    async def send_schedule_by_group(
        cls, user_id: int, user_group: str, filename: str = ""
    ) -> None:
        """A method for sending schedules by group"""
        from core.dependencies import container
        from services.image_service import ImageCreator

        actual_dates = await cls.get_dates_schedule(actual_dates=False)

        if not any(actual_dates):
            await container.bot.send_message(user_id, no_schedule)
            return

        message = await container.bot.send_message(user_id, have_schedule)

        for date in actual_dates:
            data = await cls.get_schedule(user_group, date)

            if not any(data):
                day = day_week_by_date(date)
                print(no_schedule_text.format(date=date, day=day))
                await container.bot.send_message(
                    user_id,
                    no_schedule_text.format(date=date, day=day),
                    parse_mode="HTML",
                )
                await asyncio.sleep(0.3)
                await container.bot.delete_message(user_id, message.message_id)
                continue

            user_theme = await container.db_users.get_theme_by_user_id(user_id)
            user_theme = "Classic" if user_theme not in themes_names else user_theme

            image_creator = ImageCreator()
            await image_creator.create_schedule_image(
                data=data,
                date=date,
                number_rows=len(data) + 1,
                filename=f"{user_id}{filename}",
                theme=user_theme,
            )

            photo = FSInputFile(path=f"{WORKSPACE}{user_id}{filename}.jpeg")
            await container.bot.send_photo(user_id, photo)

            (
                os.remove(f"{WORKSPACE}{user_id}{filename}.jpeg")
                if os.path.exists(f"{WORKSPACE}{user_id}{filename}.jpeg")
                else False
            )

            await asyncio.sleep(0.5)
            await container.bot.delete_message(user_id, message.message_id)
