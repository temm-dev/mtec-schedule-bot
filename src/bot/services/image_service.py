import matplotlib.pyplot as plt
import numpy as np
import random
import os
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.cbook import get_sample_data
from config.paths import WORKSPACE
from config.paths import PATH_SEASONS
from config.themes import themes_names, themes_parameters
from matplotlib import rcParams
from matplotlib.table import Table
from utils.utils import day_week_by_date


class ImageCreator:
    """A class for creating a timetable image"""

    MAX_TEXT_LENGTH = 200
    TEXT_TRUNCATE_MARKER = "..."
    SUBJECT_WRAP_WIDTH = 35
    HEADER_FONT_SIZE = 8
    BASE_FONT_SIZE = 10
    MIN_FONT_SIZE = 8

    def __init__(self) -> None:
        self._setup_matplotlib()

    @classmethod
    def _setup_matplotlib(cls) -> None:
        """Basic setup of matplotlib before getting started"""
        rcParams.update(
            {
                "figure.max_open_warning": 0,
                "figure.dpi": 150,
                "savefig.bbox": "tight",
                "savefig.format": "jpeg",
                "font.family": "sans-serif",
                "font.size": 8,
                "text.color": "black",
                "axes.edgecolor": "black",
            }
        )

        plt.switch_backend("Agg")

    @classmethod
    def _auto_font_size(cls, text: str, max_chars: int = 35) -> int:
        """A method for calculating the font size depending on the length of the text"""
        text_length = len(str(text))
        if text_length <= max_chars:
            return cls.BASE_FONT_SIZE

        scale_factor = max_chars / text_length
        return int(
            np.clip(
                cls.BASE_FONT_SIZE * scale_factor, cls.MIN_FONT_SIZE, cls.BASE_FONT_SIZE
            )
        )

    @staticmethod
    def _wrap_text(text: str, width: int) -> str:
        """A method for moving text to a new line when the maximum length is exceeded"""
        if not text:
            return ""

        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 > width:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1

        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    @staticmethod
    def _wrap_teacher_text(text: str) -> str:
        """A method for transferring the teacher's full name to a new line"""
        parts = text.rsplit(" ", 3)
        if len(parts) >= 4:
            last_three = " ".join(parts[-3:])
            if "." in last_three and len(last_three.split()) == 3:
                return f"{' '.join(parts[:-3])}\n{last_three}"
        return text

    @staticmethod
    def _validation_arguments(
        data: list,
        date: str,
        number_rows: int,
        theme: str = "Classic",
    ) -> None:
        """A method for verifying the correctness of input parameters"""
        if not data:
            raise ValueError("Data list cannot be empty")

        if not isinstance(date, str):
            raise TypeError(f"Date must be string, got {type(date).__name__}")

        if not isinstance(number_rows, int) or number_rows <= 0:
            raise TypeError("Number of rows must be positive integer")

        if theme not in themes_names:
            raise ValueError(f"Unknown theme: {theme}. Available: {themes_names}")

    @staticmethod
    def _add_seasonal_decorations(ax, season: str, num_decorations: int = 5) -> None:
        winter_imgs = os.listdir(PATH_SEASONS + "winter")
        winter_imgs.remove(".DS_Store")
        season_images = {
            "winter": winter_imgs,
            # "spring": ["branch1.png", "flower1.png", "leaf1.png"],
            # "summer": ["sun1.png", "palm1.png", "wave1.png"],
            # "autumn": ["leaf2.png", "branch2.png", "mushroom1.png"],
        }
        
        if season.lower() not in season_images:
            season = "winter"
        
        image_files = season_images[season.lower()]
        
        for _ in range(num_decorations):
            try:
                img_file = random.choice(image_files)
                img_path = os.path.join(PATH_SEASONS, season.lower(), img_file)
                
                # Load image
                img = plt.imread(img_path)
                
                img_height, img_width = img.shape[0], img.shape[1]
                
                zoom = random.uniform(0.02, 0.07)
                margin = zoom * 0.8
                
                x_pos = random.uniform(margin, 1.0 - margin)
                y_pos = random.uniform(margin, 1.0 - margin)
                
                rotation = random.uniform(0, 360)
                
                imagebox = OffsetImage(img, zoom=zoom, alpha=0.3)
                
                ab = AnnotationBbox(imagebox, (x_pos, y_pos),
                                xycoords='axes fraction',
                                frameon=False,
                                boxcoords="offset points",
                                pad=0)
                
                ab.set_clip_on(True)
                ab.set_zorder(10)
                
                ax.add_artist(ab)
                
            except FileNotFoundError:
                print(f"Warning: Decoration image not found: {img_path}")
                continue
            except Exception as e:
                print(f"Warning: Could not add decoration: {e}")
                continue

    @classmethod
    def _add_random_decorations(cls, ax, num_decorations: int = 8) -> None:
        fallback_symbols = ["❄️", "🍃", "🌸", "☀️", "🍂", "🌿", "⭐", "🎨"]
        
        for _ in range(num_decorations):
            x = random.uniform(0.05, 0.95)
            y = random.uniform(0.05, 0.95)
            
            symbol = random.choice(fallback_symbols)
            # symbol = "❄️"
            fontsize = random.randint(15, 25)
            alpha = random.uniform(0.15, 0.25)
            
            ax.text(x, y, symbol, fontsize=fontsize, alpha=alpha,
                transform=ax.transAxes, ha='center', va='center',
                color='gray', zorder=10,
                rotation=random.uniform(0, 360))

    @classmethod
    async def create_schedule_image(
        cls,
        data: list,
        date: str,
        number_rows: int,
        filename: str,
        group: str,
        theme: str = "Classic",
        add_decorations: bool = True,
        season: str = None, # type: ignore
    ) -> None:
        """A method for creating a timetable image with optional decorations"""

        cls._validation_arguments(data, date, number_rows, theme)

        day_of_week_name = day_week_by_date(date)

        columns = ["№", f"\n{group}\n\n{day_of_week_name} - {date}\n", "Ауд"]

        fig, ax = plt.subplots(figsize=(7, number_rows + 0.5))
        ax.set_axis_off()

        tbl = Table(ax, bbox=[0, 0, 1, 1])  # type: ignore
        col_widths = [0.15, 0.7, 0.15]
        height_header = 0.30
        row_height_base = (1 - height_header) / len(data)

        for col_idx, col_name in enumerate(columns):
            cell = tbl.add_cell(
                0,
                col_idx,
                col_widths[col_idx],
                row_height_base,
                text=col_name,
                loc="center",
                facecolor=themes_parameters[theme][0],
                edgecolor=themes_parameters[theme][1],
            )
            cell.get_text().set_color(themes_parameters[theme][2])
            cell.get_text().set_weight("bold")  # type: ignore
            cell.get_text().set_fontsize(10)

        for row_idx, row_data in enumerate(data, start=1):
            processed_cells = []
            max_lines = 1

            for col_idx, cell_text in enumerate(row_data):
                text = str(cell_text)

                if col_idx == 1:
                    text = cls._wrap_teacher_text(text)

                    if "\n" in text:
                        subject_part, teacher_part = text.split("\n", 1)
                        wrapped_subject = cls._wrap_text(subject_part, 35)
                        text = f"{wrapped_subject}\n{teacher_part}"
                    else:
                        text = cls._wrap_text(text, 35)

                if len(text) > 200:
                    text = text[:197] + "..."

                processed_cells.append(text)
                max_lines = max(max_lines, len(text.split("\n")))

            row_height = row_height_base * (0.3 + 0.10 * max_lines)

            for col_idx, (text, width) in enumerate(zip(processed_cells, col_widths)):
                font_size = cls._auto_font_size(text)

                cell = tbl.add_cell(
                    row_idx,
                    col_idx,
                    col_widths[col_idx],
                    row_height,
                    text=text,
                    loc="center",
                    facecolor=themes_parameters[theme][3],
                    edgecolor=themes_parameters[theme][4],
                )
                cell.get_text().set_color(themes_parameters[theme][5])
                cell.get_text().set_fontsize(font_size)
                cell.get_text().set_linespacing(1.2)

        ax.add_table(tbl)

        if add_decorations:
            if season is None:
                try:
                    month = int(date.split('.')[1]) if '.' in date else 1
                    if month in [12, 1, 2]:
                        season = "winter"
                    elif month in [3, 4, 5]:
                        season = "spring"
                    elif month in [6, 7, 8]:
                        season = "summer"
                    else:
                        season = "autumn"
                except:
                    season = "winter"  # default
            
            try:
                cls._add_random_decorations(ax, num_decorations=random.randint(10, 15))
                # cls._add_seasonal_decorations(ax, season, num_decorations=random.randint(5, 10))
            except:
                cls._add_random_decorations(ax, num_decorations=random.randint(10, 15))

        fig.patch.set_facecolor("black")
        plt.savefig(
            f"{WORKSPACE}{filename}.jpeg",
            transparent=False,
            format="jpeg",
            pad_inches=0.01,
            dpi=300,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )

        plt.close()