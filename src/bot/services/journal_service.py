"""E-journal service for MTEC schedule bot.

This module contains classes for interacting with the college's electronic journal:
web scraping, authentication, grade retrieval, and period management. Also includes
functions for processing HTML journal files and sending them to users.
"""

import asyncio
import logging
import os
import re
from typing import List, Optional, Union

import aiohttp
from aiogram.types import FSInputFile
from bs4 import BeautifulSoup

from config.paths import PATH_CSS, WORKSPACE
from config.requests_data import (
    EJOURNAL_HEADERS,
    EJOURNAL_LOGIN_URL,
    EJOURNAL_PROFILE_PERIOD_URL,
    EJOURNAL_PROFILE_URL,
)
from phrases import *
from services.database import UserRepository
from utils.formatters import format_error_message

logger = logging.getLogger(__name__)


class EJournalScraper:
    """Handles web scraping and data extraction from electronic journal."""
    
    @staticmethod
    async def _perform_login(session: aiohttp.ClientSession, login_data: dict) -> bool:
        """Authenticate with the electronic journal system.
        
        Args:
            session: aiohttp client session for HTTP requests.
            login_data: Dictionary containing login credentials.
            
        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            async with session.post(
                EJOURNAL_LOGIN_URL, data=login_data, headers=EJOURNAL_HEADERS
            ) as response:
                if response.status != 200:
                    logger.error(f"Login failed with status: {response.status}")
                    return False
                logger.info("Successfully authenticated with e-journal system")
                return True
        except aiohttp.ClientError as e:
            logger.error(f"Network error during login: {str(e)}")
            return False

    @staticmethod
    async def _save_html(content: str, file_path: str, mode: str = "w") -> None:
        """Save HTML content to file with proper error handling.
        
        Args:
            content: HTML content to save.
            file_path: Path where to save the file.
            mode: File write mode ('w' for write, 'a' for append).
        """
        try:
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)
            logger.info(f"HTML file saved: {file_path}")
        except IOError as e:
            logger.error(f"Failed to save HTML file {file_path}: {str(e)}")

    @classmethod
    async def _clean_html(cls, html: str, is_first_page: bool) -> str:
        """Clean HTML content by removing unnecessary elements.
        
        Args:
            html: Raw HTML content to clean.
            is_first_page: Whether this is the first page (affects cleaning strategy).
            
        Returns:
            Cleaned HTML content.
        """
        try:
            if is_first_page:
                return await cls._basic_clean(html)
            return await cls._head_clean(html)
        except Exception as e:
            logger.error(f"HTML cleaning failed: {str(e)}")
            return html

    @staticmethod
    async def _basic_clean(html_text: str) -> str:
        """Perform basic HTML cleaning for first page.
        
        Args:
            html_text: HTML text to clean.
            
        Returns:
            Cleaned HTML text.
        """
        soup = BeautifulSoup(html_text, "html.parser")

        # Remove navigation elements
        elements_to_remove = [
            ("a", {"class_": "navbar-brand", "href": re.compile(r"https://mtec\.by/ru/")}),
            ("form", {"class_": "d-flex", "role": "search"}),
            ("br", {}),
            ("div", {"class_": "container w-70"}),
        ]

        for tag_name, attrs in elements_to_remove:
            elements = soup.find(tag_name, **attrs)
            if elements:
                elements.decompose()

        return str(soup)

    @staticmethod
    async def _head_clean(html_text: str) -> str:
        """Clean HTML header elements for subsequent pages.
        
        Args:
            html_text: HTML text to clean.
            
        Returns:
            Cleaned HTML text.
        """
        soup = BeautifulSoup(html_text, "html.parser")
        
        # Remove navigation and container elements
        for tag_name, class_name in [
            ("nav", "navbar bg-dark"),
            ("div", "container w-70"),
        ]:
            element = soup.find(tag_name, class_=class_name)
            if element:
                element.decompose()

        return str(soup)

    @staticmethod
    async def get_periods(session: aiohttp.ClientSession) -> List[str]:
        """Extract available periods from the journal system.
        
        Args:
            session: Authenticated aiohttp client session.
            
        Returns:
            List of period IDs as strings.
        """
        try:
            async with session.get(
                EJOURNAL_PROFILE_URL, headers=EJOURNAL_HEADERS
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to get periods: {response.status}")
                    return []
                
                html = await response.text()
                periods = re.findall(r'value="(\d+)"', html)
                logger.info(f"Found {len(periods)} periods")
                return periods
        except aiohttp.ClientError as e:
            logger.error(f"Network error getting periods: {str(e)}")
            return []

    @classmethod
    async def fetch_journal(
        cls, login_data: dict[str, str], user_id: Union[int, str], all_semesters: bool = False
    ) -> bool:
        """Fetch electronic journal data for a user.
        
        Args:
            login_data: Authentication credentials.
            user_id: User identifier for file naming.
            all_semesters: Whether to fetch all semesters or current only.
            
        Returns:
            True if fetch successful, False otherwise.
        """
        output_file = f"{WORKSPACE}{user_id}.html"

        async with aiohttp.ClientSession() as session:
            # Authenticate
            if not await cls._perform_login(session, login_data):
                return False

            # Get periods if needed
            periods = []
            if all_semesters:
                periods = await cls.get_periods(session)
                if not periods:
                    logger.info("No periods found, using current semester")
                    all_semesters = False

            # Fetch journal data
            if all_semesters:
                return await cls._fetch_all_semesters(session, periods, output_file)
            return await cls._fetch_current_semester(session, output_file)

    @classmethod
    async def _fetch_current_semester(
        cls, session: aiohttp.ClientSession, output_file: str
    ) -> bool:
        """Fetch current semester journal data.
        
        Args:
            session: Authenticated aiohttp client session.
            output_file: Path to save the journal data.
            
        Returns:
            True if fetch successful, False otherwise.
        """
        try:
            async with session.get(
                EJOURNAL_PROFILE_URL, headers=EJOURNAL_HEADERS
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch current semester: {response.status}")
                    return False

                html = await response.text()
                cleaned_html = await cls._clean_html(html, True)
                await cls._save_html(cleaned_html, output_file)
                return True
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching current semester: {str(e)}")
            return False

    @classmethod
    async def _fetch_all_semesters(
        cls, session: aiohttp.ClientSession, periods: List[str], output_file: str
    ) -> bool:
        """Fetch journal data for all available semesters.
        
        Args:
            session: Authenticated aiohttp client session.
            periods: List of period IDs to fetch.
            output_file: Path to save the journal data.
            
        Returns:
            True if at least one period fetched successfully, False otherwise.
        """
        success = False
        
        for i, period in enumerate(periods):
            try:
                url = f"{EJOURNAL_PROFILE_PERIOD_URL}{period}"
                async with session.get(url, headers=EJOURNAL_HEADERS) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch period {period}: {response.status}")
                        continue

                    html = await response.text()
                    cleaned_html = await cls._clean_html(html, i == 0)
                    await cls._save_html(
                        cleaned_html, output_file, "a" if i > 0 else "w"
                    )
                    success = True
                    logger.info(f"Successfully fetched period {period}")
                    
            except aiohttp.ClientError as e:
                logger.error(f"Network error fetching period {period}: {str(e)}")
                
        return success


class JournalFileProcessor:
    """Handles file processing and user delivery for journal files."""
    
    @staticmethod
    async def inject_styles(filename: Union[str, int]) -> None:
        """Inject CSS styles into HTML journal file.
        
        Args:
            filename: Base filename (without .html extension).
        """
        file_path = f"{WORKSPACE}{filename}.html"
        css_path = f"{PATH_CSS}style.css"

        if not os.path.exists(file_path):
            logger.error(f"HTML file not found: {file_path}")
            return

        try:
            # Read HTML content
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Read CSS styles
            with open(css_path, "r", encoding="utf-8") as css_file:
                css_content = css_file.read()

            # Parse and modify HTML
            soup = BeautifulSoup(html_content, "html.parser")
            if soup.head is None:
                logger.error("HTML file missing head element")
                return

            # Add style tag
            style_tag = soup.new_tag("style")
            style_tag.string = css_content
            soup.head.append(style_tag)

            # Save modified HTML
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))

            logger.info(f"CSS styles injected into {filename}.html")
            
        except Exception as e:
            logger.error(f"Failed to inject styles: {str(e)}")

    @staticmethod
    async def send_to_user(user_id: int, all_semesters: bool = False) -> None:
        """Send journal file to user with proper error handling.
        
        Args:
            user_id: Telegram user ID.
            all_semesters: Whether to fetch all semesters or current only.
        """
        from core.dependencies import container

        file_path = None
        try:
            # Send initial message
            message1 = await container.bot.send_message(
                user_id, getting_data_journal_text
            )

            # Get user credentials and settings
            async for session in container.db_manager.get_session():
                info = await UserRepository.get_user_ejournal_info(session, user_id)
                user_settings = await UserRepository.get_user_settings(session, user_id)

            if not info or len(info) < 2:
                await container.bot.send_message(user_id, error_sending_file_text)
                return

            login_data = {"login": info[0], "password": info[1], "submit": "Войти"}
            all_semesters_flag = user_settings.get("all_semesters", False)

            # Fetch journal data
            success = await EJournalScraper.fetch_journal(
                login_data, user_id, all_semesters_flag
            )

            if not success:
                await container.bot.send_message(user_id, error_sending_file_text)
                return

            # Add styles to the generated file
            await JournalFileProcessor.inject_styles(user_id)

            # Send file to user
            message2 = await container.bot.send_message(user_id, sending_file_text)
            file_path = f"{WORKSPACE}{user_id}.html"
            
            if os.path.exists(file_path):
                await container.bot.send_document(user_id, FSInputFile(path=file_path))
                await asyncio.sleep(0.3)
                await container.bot.delete_messages(
                    user_id, [message1.message_id, message2.message_id]
                )
                logger.info(f"Journal file sent to user {user_id}")
            else:
                await container.bot.send_message(user_id, error_sending_file_text)
                logger.error(f"Generated file not found: {file_path}")

        except Exception as e:
            await container.bot.send_message(user_id, error_sending_file_text)
            logger.error(format_error_message("send_to_user", e))
        finally:
            # Clean up temporary file
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Temporary file cleaned up: {file_path}")


async def send_ejournal_file(user_id: int, all_semesters: bool = False) -> None:
    """Send e-journal file to user (legacy compatibility function).
    
    Args:
        user_id: Telegram user ID.
        all_semesters: Whether to fetch all semesters.
    """
    await JournalFileProcessor.send_to_user(user_id, all_semesters)
