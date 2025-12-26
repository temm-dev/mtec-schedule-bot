from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = (PROJECT_ROOT / "static" / "workspace").as_posix() + "/"
PATH_THEMES = (PROJECT_ROOT / "static" / "themes").as_posix() + "/"
PATH_CALL_IMG = (PROJECT_ROOT / "static" / "img").as_posix() + "/"
PATH_CSS = (PROJECT_ROOT / "static" / "css").as_posix() + "/"
PATH_DBs = (PROJECT_ROOT / "databases").as_posix() + "/"
PATH_SEASONS = (PROJECT_ROOT / "static" / "decorations").as_posix() + "/"