"""Schedule service utilities with optimized performance and security.

This module contains ScheduleService class which is responsible for requesting
and parsing schedule data from college website with proper session management,
error handling, and resource optimization.

Important:
    This module contains intentionally specific parsing and retry logic.
    The public behavior (inputs/outputs and message flow) is expected by
    other parts of application.
"""

import asyncio
import logging
import re
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional

import aiohttp
from aiogram.types import FSInputFile

from config.paths import WORKSPACE
from config.requests_data import BASE_REQUEST_HEADERS, REQUEST_DATA, REQUEST_DATA_MENTORS, REQUESTS_URL
from phrases import have_schedule, no_schedule, no_schedule_mentor_text, no_schedule_text
from utils.utils import day_week_by_date

from services.database import ScheduleArchiveRepository, UserRepository


logger = logging.getLogger(__name__)

# Constants for better maintainability
_SCHEDULE_HTML_PATH = Path(WORKSPACE) / "schedule.html"
_SCHEDULE_TXT_PATH = Path(WORKSPACE) / "schedule.txt"
_CURRENT_DATE_PATH = Path(WORKSPACE) / "current_date.txt"

# Regex patterns for parsing
_DATE_PATTERN = re.compile(r">(\d{1,2}\.\d{1,2}\.\d{4})<")
_GROUP_PATTERN = re.compile(r"([A-ZА-Я]+\d{1,3})")
_MENTOR_NAME_PATTERN = re.compile(r'value="([А-Яа-я\s]+)"')

# HTTP request configuration
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)
MAX_RETRIES = 3
RETRY_DELAY = 0.5


class ScheduleService:
    """Service for fetching, parsing, and sending schedules with optimization.

    The class methods are used across bot to:

    - Perform HTTP requests to schedule endpoint with proper error handling.
    - Parse HTML responses into a structured tabular form.
    - Read/write intermediate artifacts to workspace with resource management.
    - Render and send schedule images via bot with session management.
    - Manage database sessions efficiently using _with_session pattern.

    Important:
        This module contains intentionally specific parsing and retry logic.
        The public behavior (inputs/outputs and message flow) is expected by
        other parts of application.
    """

    def __init__(self, db_manager: Optional[Any] = None) -> None:
        """Initialize ScheduleService with optional database manager.
        
        Args:
            db_manager: Database manager instance for session management.
        """
        self.db_manager = db_manager

    async def _with_session(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a DB operation within a single acquired session.

        This helper reduces repeated session acquisition inside tight loops
        and provides consistent error handling for database operations.

        Args:
            fn: Callable that accepts session as first argument.
            *args: Positional args forwarded to fn.
            **kwargs: Keyword args forwarded to fn.

        Returns:
            The return value of fn.
            
        Raises:
            RuntimeError: If no database manager is available.
        """
        if not self.db_manager:
            from core.dependencies import container
            self.db_manager = container.db_manager
            
        async for session in self.db_manager.get_session():  # type: ignore
            return await fn(session, *args, **kwargs)

    @staticmethod
    async def _send_request(url: str, headers: dict[str, Any], data: dict[str, Any]) -> Optional[str]:
        """Send a POST request to schedule server with optimized error handling.

        This method uses a configurable retry loop with proper timeout handling
        and logging for better debugging and monitoring.

        Args:
            url: Request URL (must be valid HTTP/HTTPS URL).
            headers: HTTP request headers.
            data: POST form data.

        Returns:
            The response body as text if request succeeds.
            None if all retries are exhausted.
        """
        if not url or not isinstance(url, str):
            logger.error("URL must be a non-empty string")
            return None
            
        if not headers or not isinstance(headers, dict):
            logger.error("Headers must be a non-empty dictionary")
            return None
            
        if not data or not isinstance(data, dict):
            logger.error("Data must be a non-empty dictionary")
            return None

        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
                    async with session.post(url=url, headers=headers, data=data) as response:
                        if response.status == 200:
                            text = await response.text()
                            logger.debug(f"Request successful on attempt {attempt + 1}")
                            return text
                        else:
                            logger.warning(f"HTTP {response.status} on attempt {attempt + 1}")
                            
            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error on attempt {attempt + 1}: {e}")
            except asyncio.TimeoutError as e:
                logger.error(f"Request timeout on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
                
        logger.error(f"All {MAX_RETRIES} attempts failed for URL: {url}")
        return None

    @staticmethod
    def _validate_arguments(group: str, date: str) -> None:
        """Validate group/mentor and date arguments with comprehensive checks.

        Args:
            group: Group code or mentor name (must be non-empty string).
            date: Date string in DD.MM.YYYY format.

        Raises:
            ValueError: If any argument is invalid or doesn't match expected format.
        """
        if not isinstance(group, str) or not group.strip():
            raise ValueError('The "group" parameter must be a non-empty string.')

        if not isinstance(date, str) or not date.strip():
            raise ValueError('The "date" parameter must be a non-empty string.')
            
        date_pattern = re.compile(r'^\d{1,2}\.\d{1,2}\.\d{4}$')
        if not date_pattern.match(date.strip()):
            raise ValueError('The "date" parameter must be in DD.MM.YYYY format.')
            
        try:
            datetime.strptime(date.strip(), "%d.%m.%Y")
        except ValueError:
            raise ValueError('The "date" parameter contains an invalid date.')

    @staticmethod
    def _parse_schedule_html(html_content: str, is_mentor: bool = False) -> List[List[str]]:
        """Parse schedule HTML into a structured table with error handling.

        The parsing algorithm intentionally mirrors a legacy approach that uses
        a grep "<td " filter on an intermediate HTML file. Downstream logic
        expects the resulting table shape.

        Args:
            html_content: Raw HTML response text (must be non-empty string).
            is_mentor: If True, uses mentor parsing logic (5-column format).

        Returns:
            A list of rows, where each row is [pair, subject, room].
            Returns empty list if parsing fails.
        """
        if not isinstance(html_content, str) or not html_content.strip():
            logger.error("HTML content must be a non-empty string")
            return []
            
        try:
            with open(_SCHEDULE_HTML_PATH, "w", encoding="utf-8") as file:
                file.write(html_content)

            try:
                result = subprocess.run(
                    ['grep', '<td ', str(_SCHEDULE_HTML_PATH)],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=10
                )
                
                if result.returncode != 0:
                    logger.error(f"Grep command failed: {result.stderr}")
                    return []
                    
                with open(_SCHEDULE_TXT_PATH, "w", encoding="utf-8") as file:
                    file.write(result.stdout)
                    
            except subprocess.TimeoutExpired:
                logger.error("Grep command timed out")
                return []
            except Exception as e:
                logger.error(f"Error running grep command: {e}")
                return []

            return ScheduleService._parse_schedule_text_file(is_mentor=is_mentor)
            
        except Exception as e:
            logger.error(f"Error parsing schedule HTML: {e}")
            return []

    @staticmethod
    def _parse_schedule_text_file(is_mentor: bool = False) -> List[List[str]]:
        """Parse schedule text file into structured data with error handling.
        
        This helper method extracts common parsing logic for both group
        and mentor schedules to reduce code duplication.
        
        Args:
            is_mentor: If True, uses mentor parsing logic (5-column format).
                     If False, uses group parsing logic (4-column format).
                     
        Returns:
            List of schedule rows [pair, subject, room].
            Returns empty list if parsing fails.
        """
        try:
            with open(_SCHEDULE_TXT_PATH, "r", encoding="utf-8") as file:
                text = file.read()
                
            replacements = [
                ("        ", ""),
                ('<td class="has-text-align-center">', ""),
                ("</td>", ""),
                ('<td class="has-text-align-center text">', ""),
                ("<br>", "\n")
            ]
            
            if is_mentor:
                replacements.extend([("<b>", ""), ("</b>", "")])
            
            for old, new in replacements:
                text = text.replace(old, new)

            input_list = text.split("\n")
            if len(input_list) <= 3:
                logger.warning("Insufficient data in schedule file")
                return []
                
            input_list = input_list[3:]
            data = []
            step = 5 if is_mentor else 4
            
            for i in range(0, len(input_list), step):
                if is_mentor:
                    if i + 4 < len(input_list):
                        pair = input_list[i] + "\nпара"
                        subject = input_list[i + 1] + "\n" + input_list[i + 2]
                        room = input_list[i + 4]
                        data.append([pair, subject, room])
                else:
                    if i + 3 < len(input_list):
                        pair = input_list[i] + "\nпара"
                        subject = input_list[i + 1] + "\n" + input_list[i + 2]
                        room = input_list[i + 3]
                        data.append([pair, subject, room])

            return data
            
        except FileNotFoundError:
            logger.error("Schedule text file not found")
            return []
        except Exception as e:
            logger.error(f"Error parsing schedule text file: {e}")
            return []

    @classmethod
    async def get_dates_schedule(cls, actual_dates: bool = True) -> List[str]:
        """Get a list of available schedule dates with validation and error handling.

        Args:
            actual_dates: If True, filters out dates that are older than today.

        Returns:
            A list of date strings in DD.MM.YYYY format.
            If an error occurs, returns an empty list.
        """
        try:
            response = await cls._send_request(REQUESTS_URL, BASE_REQUEST_HEADERS, REQUEST_DATA)

            if not isinstance(response, str):
                logger.error("Response is not 'str' type - get_dates_schedule")
                return []

            dates = _DATE_PATTERN.findall(response)

            today = datetime.now().strftime("%d.%m.%Y")
            day = day_week_by_date(today)

            if day != "Воскресенье":
                dates.insert(0, today)
                dates = list(set(dates))
                dates = sorted(dates, key=lambda x: datetime.strptime(x, "%d.%m.%Y"))

            if actual_dates:
                today = date.today()
                actual_dates_list = [
                    date for date in dates 
                    if datetime.strptime(date, "%d.%m.%Y").date() >= today
                ]
                return actual_dates_list

            return dates
        except Exception as e:
            logger.error(f"Error in get_dates_schedule: {e}")
            return []

    @classmethod
    async def get_actual_current_dates(cls) -> List[str]:
        """Get available dates from locally stored current date file with error handling.

        This method reads current_date.txt from the workspace and returns
        dates that are not older than today with proper validation.

        Returns:
            A sorted list of date strings in DD.MM.YYYY format.
            If an error occurs, returns an empty list.
        """
        try:
            if not _CURRENT_DATE_PATH.exists():
                logger.warning("Current date file not found")
                return []
                
            with open(_CURRENT_DATE_PATH, "r", encoding="utf-8") as file:
                current_dates = list(set(filter(None, file.read().splitlines())))

            today = datetime.now().strftime("%d.%m.%Y")
            dates = [date for date in current_dates if date >= today]

            return sorted(dates, key=lambda x: datetime.strptime(x, "%d.%m.%Y"))
        except Exception as e:
            logger.error(f"Error in get_actual_current_dates: {e}")
            return []

    @classmethod
    async def get_groups_schedule(cls) -> List[str]:
        """Get a list of available student groups with validation and error handling.

        Returns:
            A list of group codes (e.g., "ИТ205").
            If an error occurs, returns an empty list.
        """
        try:
            response = await cls._send_request(REQUESTS_URL, BASE_REQUEST_HEADERS, REQUEST_DATA)

            if not isinstance(response, str):
                logger.error("Response is not 'str' type - get_groups_schedule")
                return []

            groups = _GROUP_PATTERN.findall(response)
            
            valid_groups = [group for group in groups if group and len(group) >= 2]
            
            return valid_groups
        except Exception as e:
            logger.error(f"Error in get_groups_schedule: {e}")
            return []

    @classmethod
    async def get_names_mentors(cls) -> List[str]:
        """Get a list of available mentor full names with validation and error handling.

        Returns:
            A list of mentor names (Cyrillic), as returned by the schedule endpoint.
            If an error occurs, returns an empty list.
        """
        try:
            response = await cls._send_request(REQUESTS_URL, BASE_REQUEST_HEADERS, REQUEST_DATA_MENTORS)

            if not isinstance(response, str):
                logger.error("Response is not 'str' type - get_names_mentors")
                return []

            mentors_names_list = _MENTOR_NAME_PATTERN.findall(response)
            
            valid_mentors = [
                name.strip() for name in mentors_names_list 
                if name and len(name.strip()) >= 3
            ]
            
            return valid_mentors
        except Exception as e:
            logger.error(f"Error in get_names_mentors: {e}")
            return []

    @classmethod
    async def get_mentors_schedule(cls, mentor_name: str, date: str) -> List[List[str]]:
        """Get mentor schedule for a specific date with validation and optimized retry logic.

        Args:
            mentor_name: Mentor full name (must be non-empty string).
            date: Date string in DD.MM.YYYY format.

        Returns:
            A parsed schedule table: list of rows [pair, subject, room].
            If schedule cannot be retrieved after retries, returns an empty list.
            
        Raises:
            ValueError: If mentor_name or date is invalid.
        """
        cls._validate_arguments(mentor_name, date)

        request_data_schedule = {
            "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "action": "sendSchedule",
            "date": date,
            "value": mentor_name,
            "rtype": "prep",
        }

        data = []
        for attempt in range(MAX_RETRIES):
            try:
                response = await cls._send_request(REQUESTS_URL, BASE_REQUEST_HEADERS, request_data_schedule)

                if isinstance(response, str):
                    data = cls._parse_schedule_html(response, is_mentor=True)

                if not data:
                    logger.warning(f"Empty schedule data for {mentor_name} on {date}, attempt {attempt + 1}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    continue

                logger.info(f"Successfully retrieved mentor schedule for {mentor_name} on {date}")
                return data
                
            except Exception as e:
                logger.error(f"Error getting mentor schedule for {mentor_name} on {date}, attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)

        logger.error(f"Failed to retrieve mentor schedule for {mentor_name} on {date} after {MAX_RETRIES} attempts")
        return data

    async def send_mentor_schedule(self, user_id: int, mentor_name: str, filename: str = "") -> None:
        """Send mentor schedule images to a user with optimized session management.

        Args:
            user_id: Telegram user ID (can be any integer, including negative for groups/channels).
            mentor_name: Mentor full name (must be non-empty string).
            filename: Optional suffix for the generated image filename.

        Raises:
            ValueError: If user_id or mentor_name is invalid.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
        if not mentor_name or not isinstance(mentor_name, str):
            raise ValueError("mentor_name must be a non-empty string")
            
        from core.dependencies import container
        from services.image_service import ImageCreator

        try:
            actual_dates = await self.get_actual_current_dates()

            if not any(actual_dates):
                await container.bot.send_message(user_id, no_schedule)
                return

            message_have_schedule_mentor = await container.bot.send_message(user_id, have_schedule)

            for date in actual_dates:
                data = await self._with_session(
                    ScheduleArchiveRepository.get_mentor_schedule, date, mentor_name
                )

                if not any(data):
                    day = day_week_by_date(date)
                    message = no_schedule_mentor_text.format(
                        mentor_name=mentor_name, date=date, day=day
                    )
                    logger.info(f"No schedule for mentor {mentor_name} on {date}")
                    await container.bot.send_message(
                        user_id, message, parse_mode="HTML"
                    )
                    continue

                user_theme = await self._with_session(
                    UserRepository.get_user_theme, user_id
                )

                image_creator = ImageCreator()
                await image_creator.create_schedule_image(
                    data=data,
                    date=date,
                    number_rows=len(data) + 1,
                    filename=f"{user_id}{filename}",
                    group=mentor_name,
                    theme=user_theme,
                )

                photo_path = Path(WORKSPACE) / f"{user_id}{filename}.jpeg"
                photo = FSInputFile(path=str(photo_path))
                await container.bot.send_photo(user_id, photo)

                if photo_path.exists():
                    photo_path.unlink()

            await container.bot.delete_message(user_id, message_have_schedule_mentor.message_id)
            
        except Exception as e:
            logger.error(f"Error sending mentor schedule to user {user_id}: {e}")
            raise

    @classmethod
    async def get_schedule(cls, group: str, date: str) -> List[List[str]]:
        """Get group schedule for a specific date with validation and optimized retry logic.

        Args:
            group: Group code (must be non-empty string).
            date: Date string in DD.MM.YYYY format.

        Returns:
            A parsed schedule table: list of rows [pair, subject, room].
            If schedule cannot be retrieved after retries, returns an empty list.
            
        Raises:
            ValueError: If group or date is invalid.
        """
        cls._validate_arguments(group, date)

        request_data_schedule = {
            "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "action": "sendSchedule",
            "date": date,
            "value": group,
            "rtype": "stds",
        }

        data = []
        for attempt in range(MAX_RETRIES):
            try:
                response = await cls._send_request(REQUESTS_URL, BASE_REQUEST_HEADERS, request_data_schedule)

                if isinstance(response, str):
                    data = cls._parse_schedule_html(response, is_mentor=False)

                if not data:
                    logger.warning(f"Empty schedule data for group {group} on {date}, attempt {attempt + 1}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    continue

                logger.info(f"Successfully retrieved group schedule for {group} on {date}")
                return data
                
            except Exception as e:
                logger.error(f"Error getting group schedule for {group} on {date}, attempt {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)

        logger.error(f"Failed to retrieve group schedule for {group} on {date} after {MAX_RETRIES} attempts")
        return data

    async def send_schedule_by_group(self, user_id: int, user_group: str, filename: str = "") -> None:
        """Send group schedule images to a user with optimized session management.

        Args:
            user_id: Telegram user ID (can be any integer, including negative for groups/channels).
            user_group: Group code (must be non-empty string).
            filename: Optional suffix for the generated image filename.

        Raises:
            ValueError: If user_id or user_group is invalid.
        """
        if not user_group or not isinstance(user_group, str):
            raise ValueError("user_group must be a non-empty string")
            
        from core.dependencies import container
        from services.image_service import ImageCreator

        try:
            actual_dates = await self.get_actual_current_dates()

            if not any(actual_dates):
                await container.bot.send_message(user_id, no_schedule)
                return

            message_have_schedule_group = await container.bot.send_message(user_id, have_schedule)

            for date in actual_dates:
                data = await self._with_session(
                    ScheduleArchiveRepository.get_student_schedule, date, user_group
                )

                if not any(data):
                    day = day_week_by_date(date)
                    message = no_schedule_text.format(
                        group=user_group, date=date, day=day
                    )
                    logger.info(f"No schedule for group {user_group} on {date}")
                    await container.bot.send_message(
                        user_id, message, parse_mode="HTML"
                    )
                    continue

                user_theme = await self._with_session(
                    UserRepository.get_user_theme, user_id
                )

                image_creator = ImageCreator()
                await image_creator.create_schedule_image(
                    data=data,
                    date=date,
                    number_rows=len(data) + 1,
                    filename=f"{user_id}{filename}",
                    group=user_group,
                    theme=user_theme,
                )

                photo_path = Path(WORKSPACE) / f"{user_id}{filename}.jpeg"
                photo = FSInputFile(path=str(photo_path))
                await container.bot.send_photo(user_id, photo)

                if photo_path.exists():
                    photo_path.unlink()

            await container.bot.delete_message(user_id, message_have_schedule_group.message_id)
            
        except Exception as e:
            logger.error(f"Error sending group schedule to user {user_id}: {e}")
            raise
