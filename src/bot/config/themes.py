"""Theme configuration module for MTEC schedule bot.

This module contains color theme parameters and image paths for schedule styling.
Used for generating schedules in various visual styles available to users.
"""

from typing import Dict, List, Final
from .paths import PATH_THEMES

# Theme color parameters [text_color, border_color, header_text, header_bg, body_border, body_text]
THEMES_PARAMETERS: Final[Dict[str, List[str]]] = {
    "Classic": ["#000", "#fff", "#fff", "#fff", "#000", "#000"],
    "MidNight": ["#131618", "#6d6d6b", "#fff", "#1d2124", "#6d6d6b", "#fff"],
    "Night": ["#131618", "#6d6d6b", "#fff", "#131618", "#6d6d6b", "#fff"],
    "LightFog": ["#F2F2F2", "#D6D6D6", "#4F4F4F", "#FFFFFF", "#E0E0E0", "#474747"],
    "Fog": ["#4A4A4A", "#6E6E6E", "#FFFFFF", "#333333", "#5A5A5A", "#EDEDED"],
    "DarkFog": ["#2E2E2E", "#474747", "#E0E0E0", "#1C1C1C", "#333333", "#E3E3E3"],
    "MtecCore": ["#508da3", "#b3b3b3", "#e3e3e3", "#ebebeb", "#b3b3b3", "#3d3d3d"],
}

# Available theme names
THEMES_NAMES: Final[List[str]] = [
    "Classic",
    "MidNight", 
    "Night",
    "LightFog",
    "Fog",
    "DarkFog",
    "MtecCore",
]

# Theme image paths
PATHS_TO_PHOTO_THEME: Final[List[str]] = [
    f"{PATH_THEMES}Classic.jpg",
    f"{PATH_THEMES}MidNight.jpg",
    f"{PATH_THEMES}Night.jpg",
    f"{PATH_THEMES}LightFog.jpg",
    f"{PATH_THEMES}Fog.jpg",
    f"{PATH_THEMES}DarkFog.jpg",
    f"{PATH_THEMES}MtecCore.jpg",
]

# Theme indices for reference
THEME_CLASSIC: Final[int] = 0
THEME_MIDNIGHT: Final[int] = 1
THEME_NIGHT: Final[int] = 2
THEME_LIGHTFOG: Final[int] = 3
THEME_FOG: Final[int] = 4
THEME_DARKFOG: Final[int] = 5
THEME_MTECCORE: Final[int] = 6

# Default theme
DEFAULT_THEME: Final[str] = "Classic"

# Theme color indices
COLOR_TEXT: Final[int] = 0
COLOR_BORDER: Final[int] = 1
COLOR_HEADER_TEXT: Final[int] = 2
COLOR_HEADER_BG: Final[int] = 3
COLOR_BODY_BORDER: Final[int] = 4
COLOR_BODY_TEXT: Final[int] = 5
