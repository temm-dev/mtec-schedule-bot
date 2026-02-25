"""
utils.py - Utility functions for schedule bot operations

Contains helper functions for date operations, memory monitoring, and name formatting.
Provides essential utilities for schedule processing, system monitoring, and data formatting.
"""

import os
from datetime import datetime
from typing import List

import psutil
from config.other import DAYS_OF_WEEK


def day_week_by_date(date: str) -> str:
    """Get the day of week name for a given date string.

    Converts a date string in DD.MM.YYYY format to the corresponding
    day of week name using the configured DAYS_OF_WEEK mapping.

    Args:
        date: Date string in the format "DD.MM.YYYY" (e.g., "25.12.2023").

    Returns:
        The day of week name as configured in DAYS_OF_WEEK.
        
    Raises:
        ValueError: If the date string is not in the expected format.
        KeyError: If the weekday number is not found in DAYS_OF_WEEK.
        
    Examples:
        >>> day_week_by_date("25.12.2023")
        'Понедельник'  # Assuming DAYS_OF_WEEK[0] = 'Понедельник'
        >>> day_week_by_date("01.01.2024")
        'Понедельник'  # Assuming January 1, 2024 was a Понедельник
    """
    try:
        date_object = datetime.strptime(date, "%d.%m.%Y")
        day_of_week_number = date_object.weekday()
        
        if day_of_week_number not in DAYS_OF_WEEK:
            raise KeyError(f"Weekday number {day_of_week_number} not found in DAYS_OF_WEEK mapping")
            
        return DAYS_OF_WEEK[day_of_week_number]
        
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date}'. Expected format: DD.MM.YYYY") from e
    except Exception as e:
        if isinstance(e, (ValueError, KeyError)):
            raise
        raise RuntimeError(f"Failed to get day of week for date '{date}': {e}") from e


def get_memory_info() -> str:
    """Get comprehensive memory usage information for server and bot process.

    Collects detailed memory statistics including total server memory, used memory,
    available memory, and process-specific memory usage (RSS and VMS).

    Returns:
        A formatted string containing memory usage information with timestamps.
        Returns error message if memory information cannot be retrieved.
        
    Raises:
        RuntimeError: If unable to access memory information due to permission issues
            or system errors.
            
    Examples:
        >>> info = get_memory_info()
        >>> isinstance(info, str)
        True
        >>> 'ОБЩАЯ ПАМЯТЬ СЕРВЕРА:' in info
        True
    """
    try:
        # Get server-wide memory information
        server_mem = psutil.virtual_memory()
        
        # Get current process memory information
        process = psutil.Process(os.getpid())
        process_mem = process.memory_info()
        
        # Calculate memory usage percentage
        process_percentage = (process_mem.rss / server_mem.total) * 100 if server_mem.total > 0 else 0
        
        # Format memory information with proper error handling for division
        total_gb = server_mem.total / (1024**3) if server_mem.total > 0 else 0
        used_gb = server_mem.used / (1024**3) if server_mem.used > 0 else 0
        available_gb = server_mem.available / (1024**3) if server_mem.available > 0 else 0
        
        rss_mb = process_mem.rss / (1024**2) if process_mem.rss > 0 else 0
        vms_mb = process_mem.vms / (1024**2) if process_mem.vms > 0 else 0
        
        info = f"""
[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]
ОБЩАЯ ПАМЯТЬ СЕРВЕРА:
    Всего: {total_gb:.2f} GB
    Используется: {used_gb:.2f} GB
    Свободно: {available_gb:.2f} GB
    Использовано (%): {server_mem.percent:.1f}%

ПАМЯТЬ ВАШЕГО БОТА (PID: {process.pid}):
    RSS (физическая): {rss_mb:.2f} MB
    VMS (виртуальная): {vms_mb:.2f} MB
    Доля от общей (%): {process_percentage:.2f}%
    """.strip()
        
        return info
        
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        raise RuntimeError(f"Unable to access process memory information: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve memory information: {e}") from e


def format_names(names: List[str]) -> List[str]:
    """Format full names to initials format (Surname N. P.).

    Converts full names in format "Surname Firstname Patronymic" to
    "Surname N. P." format. Names that don't have at least 3 parts
    are left unchanged.

    Args:
        names: List of full name strings to format.

    Returns:
        List of formatted names. Names with insufficient parts are returned
        unchanged. Empty or None values are handled gracefully.
        
    Raises:
        TypeError: If names is not a list or contains non-string elements.
        
    Examples:
        >>> format_names(["Иванов Иван Иванович", "Петров Петр"])
        ['Иванов И. И.', 'Петров Петр']
        >>> format_names(["Сидоров А. Б."])
        ['Сидоров А. Б.']
        >>> format_names([])
        []
    """
    if not isinstance(names, list):
        raise TypeError("names must be a list")
    
    result = []
    
    for index, name in enumerate(names):
        try:
            # Handle None or empty values
            if not isinstance(name, str):
                if name is None:
                    result.append("")
                    continue
                raise TypeError(f"Name at index {index} is not a string: {type(name)}")
            
            if not name.strip():
                result.append(name)
                continue
            
            # Split name into parts and format
            parts = name.strip().split()
            if len(parts) >= 3:
                surname, first_name, patronymic = parts[0], parts[1], parts[2]
                
                # Ensure we have characters to extract initials from
                first_initial = first_name[0] + "." if first_name else ""
                patronymic_initial = patronymic[0] + "." if patronymic else ""
                
                formatted_name = f"{surname} {first_initial} {patronymic_initial}".strip()
                result.append(formatted_name)
            else:
                # Leave names with insufficient parts unchanged
                result.append(name)
                
        except (IndexError, AttributeError) as e:
            # Handle malformed names gracefully
            result.append(name)  # Return original name on error
            continue
        except Exception as e:
            if isinstance(e, TypeError):
                raise
            # Handle any other unexpected errors gracefully
            result.append(name)
            continue
    
    return result
