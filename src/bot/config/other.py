"""Application constants and day mappings for MTEC schedule bot.

This module contains various configuration parameters and constants used throughout
the application, including day of week mappings and other static data.
"""

from typing import Dict, Final

DAYS_OF_WEEK: Final[Dict[int, str]] = {
    0: "Понедельник",
    1: "Вторник", 
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}