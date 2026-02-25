"""
markup.py - Utilities for creating keyboards and media groups

Contains functions and variables for creating inline keyboards, reply keyboards 
and media groups for the bot. Includes dynamic keyboards for selecting groups and 
mentors, as well as static keyboards for menu and administrative panel.
"""

import asyncio
import copy
import re

import aiofiles
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.media_group import MediaGroupBuilder
from config.paths import PATH_CALL_IMG, WORKSPACE
from config.themes import PATHS_TO_PHOTO_THEME, THEMES_PARAMETERS

from .keyboard import build_multi_column_keyboard
from .utils import format_names

# Global variables for dynamically created keyboards
_mentors_dict: dict[str, str] | None = None
_inline_markup_select_group: InlineKeyboardMarkup | None = None
_inline_markup_select_mentors_names: InlineKeyboardMarkup | None = None
_inline_markup_select_mentors_fcs: InlineKeyboardMarkup | None = None
_initialization_lock = asyncio.Lock()
_initialized = False

# Pre-compiled regex pattern for better performance
_GROUP_SORT_PATTERN = re.compile(r"([A-ZА-Я]+)(\d+)")


def sort_key(group: str) -> tuple[str, int]:
    """Generate sorting key for groups and mentors by letters and numbers.
    
    This function extracts alphabetical and numerical parts from strings like
    "ПО-11" or "Иванов И.И." to enable proper sorting. For strings without
    a clear letter-number pattern, it returns the string with a default number.
    
    Args:
        group: String to sort (e.g., "ПО-11", "Иванов И.И.", or just "Иванов")
        
    Returns:
        A tuple (letters, number) for sorting where letters is the alphabetical
        part and number is the numerical part (or 0 if not found).
        
    Examples:
        >>> sort_key("ПО-11")
        ('ПО', 11)
        >>> sort_key("Иванов И.И.")
        ('Иванов И.И.', 0)
        >>> sort_key("АБ123")
        ('АБ', 123)
    """
    match = _GROUP_SORT_PATTERN.match(group)
    if match:
        letters = match.group(1)
        numbers = match.group(2)
        return (letters, int(numbers))
    return (group, 0)


async def get_groups_schedule_wrapper() -> list[str]:
    """Get sorted list of groups from schedule service.
    
    Retrieves groups from the schedule service, removes duplicates, and sorts
    them using the sort_key function for proper ordering.
    
    Returns:
        A sorted list of unique group names.
        
    Raises:
        RuntimeError: If unable to retrieve groups from the schedule service.
    """
    try:
        from services.schedule_service import ScheduleService
        
        schedule_service = ScheduleService()
        groups = await schedule_service.get_groups_schedule()
        
        if not groups:
            return []
            
        # Remove duplicates and sort
        unique_groups = sorted(set(groups), key=sort_key)
        return unique_groups
        
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve groups from schedule service: {e}") from e


async def get_mentors_names_schedule_wrapper() -> dict[str, str]:
    """Get dictionary of mentors {initials: full name} from schedule service.
    
    Retrieves mentor names from the schedule service, formats them to initials,
    saves to file for caching, and returns a dictionary mapping initials to full names.
    
    Returns:
        A dictionary where keys are mentor initials and values are full names.
        
    Raises:
        RuntimeError: If unable to retrieve mentors from the schedule service
            or if file operations fail.
        IOError: If unable to write mentors to file.
    """
    try:
        from services.schedule_service import ScheduleService
        
        schedule_service = ScheduleService()
        mentors_names = await schedule_service.get_names_mentors()
        
        if not mentors_names:
            return {}
            
        # Save mentors to file for caching
        try:
            async with aiofiles.open(
                f"{WORKSPACE}all_mentors.txt", "w", encoding="utf-8"
            ) as file:
                for mentor in mentors_names:
                    await file.write(f"{mentor}\n")
        except IOError as e:
            raise IOError(f"Failed to write mentors to file: {e}") from e
        
        # Create initials to full name mapping
        mentors_initials = format_names(mentors_names)
        mentors_dict = dict(zip(mentors_initials, mentors_names))
        
        return mentors_dict
        
    except Exception as e:
        if isinstance(e, (RuntimeError, IOError)):
            raise
        raise RuntimeError(f"Failed to retrieve mentors from schedule service: {e}") from e


async def _ensure_initialized() -> None:
    """Ensure dynamic data is initialized with thread safety.
    
    This function initializes all dynamic keyboard data including mentors dictionary
    and group selection keyboards. It uses async locks to prevent race conditions
    during initialization and handles errors gracefully.
    
    Raises:
        RuntimeError: If initialization fails due to service errors or file operations.
        IOError: If unable to write groups to file.
    """
    global _mentors_dict, _inline_markup_select_group, _initialized
    global _inline_markup_select_mentors_names, _inline_markup_select_mentors_fcs
    
    if _initialized:
        return
        
    async with _initialization_lock:
        if _initialized:
            return
            
        try:
            # Initialize mentors data
            _mentors_dict = await get_mentors_names_schedule_wrapper()
            
            # Initialize groups data and save to file
            groups = await get_groups_schedule_wrapper()
            try:
                async with aiofiles.open(
                    f"{WORKSPACE}all_groups.txt", "w", encoding="utf-8"
                ) as file:
                    for group in groups:
                        await file.write(f"{group}\n")
            except IOError as e:
                raise IOError(f"Failed to write groups to file: {e}") from e
            
            # Create group selection keyboard
            _inline_markup_select_group = InlineKeyboardMarkup(
                inline_keyboard=build_multi_column_keyboard(groups)
            )
            
            # Create mentor keyboards if mentors data exists
            if _mentors_dict:
                # Keyboard for full names
                mentors_names = sorted(set(_mentors_dict.values()), key=sort_key)
                _inline_markup_select_mentors_names = InlineKeyboardMarkup(
                    inline_keyboard=build_multi_column_keyboard(mentors_names)
                )
                
                # Keyboard for initials
                mentors_fcs = sorted(set(_mentors_dict.keys()), key=sort_key)
                _inline_markup_select_mentors_fcs = InlineKeyboardMarkup(
                    inline_keyboard=build_multi_column_keyboard(mentors_fcs)
                )
            else:
                # Handle empty mentors case
                _inline_markup_select_mentors_names = InlineKeyboardMarkup(inline_keyboard=[])
                _inline_markup_select_mentors_fcs = InlineKeyboardMarkup(inline_keyboard=[])
            
            _initialized = True
            
        except Exception as e:
            if isinstance(e, (RuntimeError, IOError)):
                raise
            raise RuntimeError(f"Failed to initialize dynamic data: {e}") from e


async def get_mentors_dict() -> dict[str, str]:
    """Get mentors dictionary, initializing on first call.
    
    Returns a dictionary mapping mentor initials to full names.
    Initializes the data if this is the first call.
    
    Returns:
        Dictionary with mentor initials as keys and full names as values.
        Returns empty dict if initialization fails.
    """
    try:
        await _ensure_initialized()
        return _mentors_dict.copy() if _mentors_dict else {}
    except Exception:
        # Return empty dict on initialization failure to prevent crashes
        return {}


async def get_inline_markup_select_group() -> InlineKeyboardMarkup:
    """Get group selection keyboard, initializing on first call.
    
    Returns an inline keyboard for group selection.
    Initializes the keyboard data if this is the first call.
    
    Returns:
        InlineKeyboardMarkup for group selection.
        Returns empty keyboard if initialization fails.
    """
    try:
        await _ensure_initialized()
        return _inline_markup_select_group or InlineKeyboardMarkup(inline_keyboard=[])
    except Exception:
        # Return empty keyboard on initialization failure to prevent crashes
        return InlineKeyboardMarkup(inline_keyboard=[])


async def get_inline_markup_select_mentors_names() -> InlineKeyboardMarkup:
    """Get mentor selection keyboard by full names, initializing on first call.
    
    Returns an inline keyboard for selecting mentors by their full names.
    Initializes the keyboard data if this is the first call.
    
    Returns:
        InlineKeyboardMarkup for mentor selection by full names.
        Returns empty keyboard if initialization fails.
    """
    try:
        await _ensure_initialized()
        return _inline_markup_select_mentors_names or InlineKeyboardMarkup(inline_keyboard=[])
    except Exception:
        # Return empty keyboard on initialization failure to prevent crashes
        return InlineKeyboardMarkup(inline_keyboard=[])


async def get_inline_markup_select_mentors_fcs() -> InlineKeyboardMarkup:
    """Get mentor selection keyboard by initials, initializing on first call.
    
    Returns an inline keyboard for selecting mentors by their initials.
    Initializes the keyboard data if this is the first call.
    
    Returns:
        InlineKeyboardMarkup for mentor selection by initials.
        Returns empty keyboard if initialization fails.
    """
    try:
        await _ensure_initialized()
        return _inline_markup_select_mentors_fcs or InlineKeyboardMarkup(inline_keyboard=[])
    except Exception:
        # Return empty keyboard on initialization failure to prevent crashes
        return InlineKeyboardMarkup(inline_keyboard=[])


async def refresh_dynamic_data() -> None:
    """Force refresh of all dynamic keyboard data.
    
    Resets the initialization flag and reinitializes all dynamic data
    including mentors dictionary and group selection keyboards.
    
    Raises:
        RuntimeError: If refresh operation fails.
    """
    global _initialized
    try:
        _initialized = False
        await _ensure_initialized()
    except Exception as e:
        raise RuntimeError(f"Failed to refresh dynamic data: {e}") from e


# Статические inline-клавиатуры
inline_status_list = [
    [
        InlineKeyboardButton(text="👩‍🏫 Преподаватель", callback_data="👩‍🏫 Преподаватель"),
        InlineKeyboardButton(text="👨‍🎓 Студент", callback_data="👨‍🎓 Студент"),
    ]
]

inliine_markup_select_status = InlineKeyboardMarkup(inline_keyboard=inline_status_list)

inline_markup_select_theme = InlineKeyboardMarkup(
    inline_keyboard=build_multi_column_keyboard(list(THEMES_PARAMETERS.keys()))
)


inline_additional_functions_list = [
    [InlineKeyboardButton(text="🌐 Сайт колледжа", url="https://mtec.by/ru/")],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="📆 Расписание")],
    [
        InlineKeyboardButton(text="👨‍🎓 Учащиеся", url="https://mtec.by/ru/students/schedule"),
        InlineKeyboardButton(text="🧑‍🏫 Преподаватели", url="https://mtec.by/ru/workers/schedule"),
    ],
]

inline_additional_functions_list_extended = [
    [InlineKeyboardButton(text="🌐 Сайт колледжа", url="https://mtec.by/ru/")],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="📆 Расписание")],
    [
        InlineKeyboardButton(text="👨‍🎓 Учащиеся", url="https://mtec.by/ru/students/schedule"),
        InlineKeyboardButton(text="🧑‍🏫 Преподаватели", url="https://mtec.by/ru/workers/schedule"),
    ],
    [InlineKeyboardButton(text="📑 Справки", url="http://178.124.196.1:84/anketa/Home/Spravka")],
]

inline_additional_functions_bot = [
    [InlineKeyboardButton(text="⚙️ Настройки", callback_data="⚙️ Настройки")],
    [InlineKeyboardButton(text="⚖️ Правовая информация", callback_data="⚖️ Правовая информация")],
]

inline_additional_functions_social_networks_list = [
    [
        InlineKeyboardButton(text="Instagram", url="https://www.instagram.com/mtecby/"),
        InlineKeyboardButton(text="TikTok", url="https://www.tiktok.com/@mtec_molo"),
    ],
    [
        InlineKeyboardButton(
            text="YouTube",
            url="https://www.youtube.com/channel/UC4B6JgjjmeZrhMnGlAx9bew",
        ),
        InlineKeyboardButton(text="Facebook", url="https://www.facebook.com/mtecbks/"),
    ],
    [InlineKeyboardButton(text="Vk", url="https://vk.com/mtecby")],
]

inline_markup_additional_functions = InlineKeyboardMarkup(inline_keyboard=inline_additional_functions_list)
inline_markup_additional_functions_extended = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_list_extended
)
inline_markup_additional_functions_bot = InlineKeyboardMarkup(inline_keyboard=inline_additional_functions_bot)
inline_markup_additional_functions_social_networks = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_social_networks_list
)


# Reply-клавиатуры
reply_additional_functions_list = [
    [
        KeyboardButton(text="🕒 Расписание звонков"),
        KeyboardButton(text="📚 Моё расписание"),
    ],
    [
        KeyboardButton(text="👩‍🏫 Расписание преподавателя"),
        KeyboardButton(text="👥 Расписание группы"),
    ],
    [KeyboardButton(text="📖 Электронный журнал")],
    [KeyboardButton(text="🔍 Дополнительно"), KeyboardButton(text="💬 Помощь")],
]

reply_markup_additional_functions = ReplyKeyboardMarkup(keyboard=reply_additional_functions_list)

reply_additional_functions_list_admin = copy.deepcopy(reply_additional_functions_list)
reply_additional_functions_list_admin.append([KeyboardButton(text="⚙️ Админ панель")])
reply_markup_additional_functions_admin = ReplyKeyboardMarkup(keyboard=reply_additional_functions_list_admin)


# Административная панель
inline_admin_panel_tools_list = [
    [InlineKeyboardButton(text="🗂️ DATABASE 🗂️", callback_data="🗂️ DATABASE 🗂️")],
    [InlineKeyboardButton(text="📊 Memory usage", callback_data="📊 Memory usage")],
    [
        InlineKeyboardButton(text="users 📄", callback_data="users 📄"),
        InlineKeyboardButton(text="hashes 📄", callback_data="hashes 📄"),
    ],
    [
        InlineKeyboardButton(text="logs 📄", callback_data="logs 📄"),
        InlineKeyboardButton(text="support 📄", callback_data="support 📄"),
    ],
    [InlineKeyboardButton(text="⼈ USERS ⼈", callback_data="⼈ USERS ⼈")],
    [
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data="🚫 Заблокировать"),
        InlineKeyboardButton(text="Сообщение 👤", callback_data="Сообщение 👤"),
    ],
    [
        InlineKeyboardButton(text="Сообщение 👥", callback_data="Сообщение 👥"),
        InlineKeyboardButton(text="Сообщение 🫂", callback_data="Сообщение 🫂"),
    ],
]
inline_markup_admin_panel_tools = InlineKeyboardMarkup(inline_keyboard=inline_admin_panel_tools_list)


# Media groups with lazy initialization
_media_photo_themes = None
_media_call_schedule_photos = None


def _build_media_photo_themes():
    """Create media group with theme images.
    
    Builds a media group containing all theme preview images.
    
    Returns:
        MediaGroup containing theme preview images.
        
    Raises:
        FileNotFoundError: If theme image files are not found.
        IOError: If unable to read image files.
    """
    try:
        builder = MediaGroupBuilder()
        for photo_path in PATHS_TO_PHOTO_THEME:
            try:
                builder.add(type="photo", media=FSInputFile(path=photo_path))  # type: ignore
            except (FileNotFoundError, IOError) as e:
                raise IOError(f"Failed to load theme image from {photo_path}: {e}") from e
        return builder.build()
    except Exception as e:
        if isinstance(e, IOError):
            raise
        raise RuntimeError(f"Failed to build media photo themes: {e}") from e


def _build_media_call_schedule_photos():
    """Create media group with call schedule images.
    
    Builds a media group containing call schedule photo images.
    
    Returns:
        MediaGroup containing call schedule images.
        
    Raises:
        FileNotFoundError: If call schedule image files are not found.
        IOError: If unable to read image files.
    """
    try:
        builder = MediaGroupBuilder()
        
        # Add first call schedule photo
        photo1_path = f"{PATH_CALL_IMG}call_schedule_photo1.png"
        try:
            builder.add(type="photo", media=FSInputFile(path=photo1_path))  # type: ignore
        except (FileNotFoundError, IOError) as e:
            raise IOError(f"Failed to load call schedule photo 1 from {photo1_path}: {e}") from e
            
        # Add second call schedule photo
        photo2_path = f"{PATH_CALL_IMG}call_schedule_photo2.png"
        try:
            builder.add(type="photo", media=FSInputFile(path=photo2_path))  # type: ignore
        except (FileNotFoundError, IOError) as e:
            raise IOError(f"Failed to load call schedule photo 2 from {photo2_path}: {e}") from e
            
        return builder.build()
    except Exception as e:
        if isinstance(e, IOError):
            raise
        raise RuntimeError(f"Failed to build media call schedule photos: {e}") from e


def get_media_photo_themes():
    """Get media group with theme images (lazy initialization).
    
    Returns a media group containing all theme preview images.
    Builds the media group only on first call for efficiency.
    
    Returns:
        MediaGroup containing theme preview images.
        Returns None if media group creation fails.
    """
    global _media_photo_themes
    if _media_photo_themes is None:
        try:
            _media_photo_themes = _build_media_photo_themes()
        except Exception:
            # Return None on failure to prevent crashes
            _media_photo_themes = None
    return _media_photo_themes


def get_media_call_schedule_photos():
    """Get media group with call schedule images (lazy initialization).
    
    Returns a media group containing call schedule photo images.
    Builds the media group only on first call for efficiency.
    
    Returns:
        MediaGroup containing call schedule images.
        Returns None if media group creation fails.
    """
    global _media_call_schedule_photos
    if _media_call_schedule_photos is None:
        try:
            _media_call_schedule_photos = _build_media_call_schedule_photos()
        except Exception:
            # Return None on failure to prevent crashes
            _media_call_schedule_photos = None
    return _media_call_schedule_photos