"""Bot settings configuration module for MTEC schedule bot.

This module contains text configurations for various bot settings and toggles.
Each setting defines the text displayed for enabled and disabled states.
"""

from typing import Dict, List, Final

# Settings text mappings (disabled_state, enabled_state)
SETTINGS_DICT_TEXT: Final[Dict[str, List[str]]] = {
    "toggle_schedule": ["📆 Рассылка расписания ❌", "📆 Рассылка расписания ✅"],
    "all_semesters": ["📙 Все семестры ❌", "📙 Все семестры ✅"],
}

# Setting keys for reference
SETTING_TOGGLE_SCHEDULE: Final[str] = "toggle_schedule"
SETTING_ALL_SEMESTERS: Final[str] = "all_semesters"

# Setting states
STATE_DISABLED: Final[int] = 0
STATE_ENABLED: Final[int] = 1

# Default settings values
DEFAULT_SETTINGS: Final[Dict[str, bool]] = {
    SETTING_TOGGLE_SCHEDULE: True,
    SETTING_ALL_SEMESTERS: False,
}
