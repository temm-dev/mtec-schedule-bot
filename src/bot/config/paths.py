"""Path configuration module for MTEC schedule bot.

This module contains absolute paths to all project directories used for accessing
static files, themes, images, databases, and seasonal decorations.
"""


from pathlib import Path
from typing import Final

# Project root directory
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

# Static directories
WORKSPACE: Final[str] = (PROJECT_ROOT / "static" / "workspace").as_posix() + "/"
PATH_THEMES: Final[str] = (PROJECT_ROOT / "static" / "themes").as_posix() + "/"
PATH_CALL_IMG: Final[str] = (PROJECT_ROOT / "static" / "img").as_posix() + "/"
PATH_CSS: Final[str] = (PROJECT_ROOT / "static" / "css").as_posix() + "/"
PATH_SEASONS: Final[str] = (PROJECT_ROOT / "static" / "decorations").as_posix() + "/"

# Database directory
PATH_DBs: Final[str] = (PROJECT_ROOT / "databases").as_posix() + "/"

# File paths for reference
WORKSPACE_DIR: Final[Path] = PROJECT_ROOT / "static" / "workspace"
THEMES_DIR: Final[Path] = PROJECT_ROOT / "static" / "themes"
IMAGES_DIR: Final[Path] = PROJECT_ROOT / "static" / "img"
CSS_DIR: Final[Path] = PROJECT_ROOT / "static" / "css"
SEASONS_DIR: Final[Path] = PROJECT_ROOT / "static" / "decorations"
DATABASES_DIR: Final[Path] = PROJECT_ROOT / "databases"
