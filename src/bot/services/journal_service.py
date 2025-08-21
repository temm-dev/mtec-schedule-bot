import logging
import os
import re

import aiohttp
from aiogram.types import FSInputFile
from bs4 import BeautifulSoup
from config.paths import PATH_CSS, WORKSPACE
from config.requests_data import (
    ejournal_headers,
    ejournal_login_url,
    ejournal_profile_period_url,
    ejournal_profile_url,
)
from phrases import *
from utils.formatters import format_error_message

logger = logging.getLogger(__name__)


class EJournalScraper:
    """A class for working with an electronic journal"""

    @staticmethod
    async def _perform_login(session: aiohttp.ClientSession, login_data: dict) -> bool:
        """The method for logging in"""
        try:
            async with session.post(
                ejournal_login_url, data=login_data, headers=ejournal_headers
            ) as response:
                if response.status != 200:
                    logger.error(f"Ошибка входа: {response.status}")
                    return False
                logger.info("Успешный вход в систему")
                return True
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при входе: {str(e)}")
            return False

    @staticmethod
    async def _save_html(content: str, file_path: str, mode: str = "w") -> None:
        """A method for saving HTML to a file"""
        try:
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Файл сохранен: {file_path}")
        except IOError as e:
            logger.error(f"Ошибка записи файла: {file_path}, {str(e)}")

    @classmethod
    async def _clean_html(cls, html: str, is_first_page: bool) -> str:
        """A method for cleaning HTML from unnecessary elements"""
        try:
            if is_first_page:
                return await cls._basic_clean(html)
            return await cls._head_clean(html)
        except Exception as e:
            logger.error(f"Ошибка очистки HTML: {str(e)}")
            return html

    @staticmethod
    async def _basic_clean(html_text: str) -> str:
        """A method for basic HTML cleaning"""
        soup = BeautifulSoup(html_text, "html.parser")

        navbar = soup.find(
            "a", class_="navbar-brand", href=re.compile(r"https://mtec\.by/ru/")
        )
        if navbar:
            navbar.decompose()

        search_form = soup.find("form", class_="d-flex", role="search")
        if search_form:
            search_form.decompose()
        
        br_tag = soup.find("br")
        if br_tag:
            br_tag.decompose()
        
        br_tag = soup.find("br")
        if br_tag:
            br_tag.decompose()
        
        div_container = soup.find("div", class_="container w-70")
        if div_container:
            div_container.decompose()

        return str(soup)

    @staticmethod
    async def _head_clean(html_text: str) -> str:
        """A method for clearing the HTML header"""
        soup = BeautifulSoup(html_text, "html.parser")
        nav_tag = soup.find("nav", class_="navbar bg-dark")
        div_tag = soup.find("div", class_="container w-70")

        if nav_tag:
            nav_tag.decompose()
        
        if div_tag:
            div_tag.decompose()

        return str(soup)

    @staticmethod
    async def get_periods(session: aiohttp.ClientSession) -> list[str]:
        """Method for getting a list of periods"""
        try:
            async with session.get(
                ejournal_profile_url, headers=ejournal_headers
            ) as response:
                if response.status != 200:
                    logger.error(f"Ошибка получения периодов: {response.status}")
                    return []
                html = await response.text()
                return re.findall(r'value="(\d+)"', html)
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при получении периодов: {str(e)}")
            return []

    @classmethod
    async def fetch_journal(
        cls, login_data: dict[str, str], user_id: int | str, all_semesters: bool = False
    ) -> bool:
        """A method for obtaining an electronic journal"""
        user_file = f"{WORKSPACE}{user_id}.html"

        async with aiohttp.ClientSession() as session:
            # Аутентификация
            if not await cls._perform_login(session, login_data):
                return False

            # Получение периодов
            periods = []
            if all_semesters:
                periods = await cls.get_periods(session)
                if not periods:
                    logger.info("Не найдены периоды, используется текущий семестр")
                    all_semesters = False

            # Получение данных журнала
            if all_semesters:
                return await cls._fetch_all_semesters(session, periods, user_file)
            return await cls._fetch_current_semester(session, user_file)

    @classmethod
    async def _fetch_current_semester(
        cls, session: aiohttp.ClientSession, output_file: str
    ) -> bool:
        """A method for getting data for the current semester"""
        try:
            async with session.get(
                ejournal_profile_url, headers=ejournal_headers
            ) as response:
                if response.status != 200:
                    logger.error(f"Ошибка получения журнала: {response.status}")
                    return False

                html = await response.text()
                cleaned_html = await cls._clean_html(html, True)
                await cls._save_html(cleaned_html, output_file)
                return True
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка получения текущего семестра: {str(e)}")
            return False

    @classmethod
    async def _fetch_all_semesters(
        cls, session: aiohttp.ClientSession, periods: list[str], output_file: str
    ) -> bool:
        """A method for obtaining data for all semesters"""
        success = False
        for i, period in enumerate(periods):
            try:
                url = f"{ejournal_profile_period_url}{period}"
                async with session.get(url, headers=ejournal_headers) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка периода {period}: {response.status}")
                        continue

                    html = await response.text()
                    cleaned_html = await cls._clean_html(html, i == 0)
                    await cls._save_html(
                        cleaned_html, output_file, "a" if i > 0 else "w"
                    )
                    success = True
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка периода {period}: {str(e)}")
        return success


class JournalFileProcessor:
    """A class for processing log files"""

    @staticmethod
    async def inject_styles(filename: str | int) -> None:
        """A method for adding CSS styles to an HTML file"""

        file_path = f"{WORKSPACE}{filename}.html"
        css_path = f"{PATH_CSS}style.css"

        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            return

        try:
            # Чтение HTML
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Чтение CSS
            with open(css_path, "r") as css_file:
                css_content = css_file.read()

            # Вставка стилей
            soup = BeautifulSoup(html_content, "html.parser")
            if soup.head is None:
                logger.error("Отсутствует head в HTML")
                return

            style_tag = soup.new_tag("style")
            style_tag.string = css_content
            soup.head.append(style_tag)

            # Сохранение результата
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))

            logger.info(f"Стили добавлены в {filename}.html")
        except Exception as e:
            logger.error(f"Ошибка добавления стилей: {str(e)}")

    @staticmethod
    async def send_to_user(user_id: int, all_semesters: bool = False) -> None:
        """The method for sending the log file to the user"""
        from core.dependencies import container

        try:
            await container.bot.send_message(user_id, getting_data_journal_text)

            # Получение данных пользователя
            info = container.db_users.get_user_ejournal_info(user_id)
            user_settings = container.db_users.get_user_settigs(user_id)

            login_data = {"login": info[0], "password": info[1], "submit": "Войти"}
            all_semesters_flag = bool(user_settings["all_semesters"]) or all_semesters

            # Получение журнала
            success = await EJournalScraper.fetch_journal(
                login_data, user_id, all_semesters_flag
            )

            if not success:
                await container.bot.send_message(user_id, error_sending_file_text)
                return

            # Обработка файла
            await JournalFileProcessor.inject_styles(user_id)
            await container.bot.send_message(user_id, sending_file_text)

            # Отправка файла
            file_path = f"{WORKSPACE}{user_id}.html"
            if os.path.exists(file_path):
                await container.bot.send_document(user_id, FSInputFile(path=file_path))
            else:
                await container.bot.send_message(user_id, error_sending_file_text)

        except Exception as e:
            await container.bot.send_message(user_id, error_sending_file_text)
            logger.error(format_error_message("send_to_user", e))
        finally:
            # Очистка временного файла
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Временный файл удален: {file_path}")


async def get_journal(login_data, user_id, periods=None, all_semesters=False):
    return await EJournalScraper.fetch_journal(login_data, user_id, all_semesters)


async def get_periods_journal(login_data):
    async with aiohttp.ClientSession() as session:
        if not await EJournalScraper._perform_login(session, login_data):
            return []
        return await EJournalScraper.get_periods(session)


async def add_journal_style(filename):
    await JournalFileProcessor.inject_styles(filename)


async def send_ejournal_file(user_id, all_semesters=False):
    await JournalFileProcessor.send_to_user(user_id, all_semesters)
