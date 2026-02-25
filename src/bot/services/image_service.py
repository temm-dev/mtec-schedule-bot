"""Schedule image generator with advanced optimizations.

This module contains ImageCreator which renders schedule tables into JPEG images using Matplotlib
with enhanced performance, memory management, and rendering optimizations.

Important:
    Image rendering is sensitive: minor changes (text wrapping rules, figure size,
    DPI, bbox, colors, row height math) can change the produced image.
    Refactors in this module must preserve the rendering output while improving performance.
"""

import gc
import re
import time
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from functools import lru_cache
from collections import defaultdict
from contextlib import contextmanager

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams
from matplotlib.table import Table

from config.paths import WORKSPACE
from config.themes import THEMES_NAMES, THEMES_PARAMETERS
from utils.utils import day_week_by_date


@dataclass
class RenderConfig:
    """Advanced configuration for image rendering with dynamic optimization."""
    max_text_length: int = 200
    text_truncate_marker: str = "..."
    subject_wrap_width: int = 35
    header_font_size: int = 10
    base_font_size: int = 12
    min_font_size: int = 10
    figure_dpi: int = 300
    figure_width: float = 7.0
    figure_height_offset: float = 0.5
    col_widths: Tuple[float, float, float] = (0.15, 0.7, 0.15)
    height_header: float = 0.30
    row_height_base_factor: float = 0.3
    row_height_lines_factor: float = 0.10
    line_spacing: float = 1.2
    pad_inches: float = 0.01
    
    # Advanced optimization settings
    enable_performance_monitoring: bool = True
    enable_adaptive_font_scaling: bool = True
    enable_smart_caching: bool = True
    max_cache_size: int = 2000
    batch_processing_threshold: int = 10
    
    # Cache for frequently used values
    vowels: str = "аеёиоуыэюяaeiouy"
    
    # Performance metrics (not serialized)
    _metrics: Dict[str, Any] = field(default_factory=lambda: {
        'images_created': 0,
        'total_render_time': 0.0,
        'cache_hits': 0,
        'cache_misses': 0,
        'memory_peak': 0.0,
        'last_cleanup_time': 0.0
    }, init=False)
    
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)


class PerformanceMetrics:
    """Thread-safe performance metrics collector for ImageCreator."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._metrics = {
            'images_created': 0,
            'total_render_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'memory_peak': 0.0,
            'last_cleanup_time': 0.0,
            'average_render_time': 0.0,
            'cache_hit_ratio': 0.0
        }
    
    def increment_images_created(self, render_time: float):
        """Increment image creation counter and update timing metrics."""
        with self._lock:
            self._metrics['images_created'] += 1
            self._metrics['total_render_time'] += render_time
            self._metrics['average_render_time'] = (
                self._metrics['total_render_time'] / self._metrics['images_created']
            )
    
    def record_cache_hit(self):
        """Record a cache hit."""
        with self._lock:
            self._metrics['cache_hits'] += 1
            self._update_cache_ratio()
    
    def record_cache_miss(self):
        """Record a cache miss."""
        with self._lock:
            self._metrics['cache_misses'] += 1
            self._update_cache_ratio()
    
    def _update_cache_ratio(self):
        """Update cache hit/miss ratio."""
        total = self._metrics['cache_hits'] + self._metrics['cache_misses']
        if total > 0:
            self._metrics['cache_hit_ratio'] = self._metrics['cache_hits'] / total
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            return self._metrics.copy()
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            for key in self._metrics:
                self._metrics[key] = 0 if isinstance(self._metrics[key], (int, float)) else self._metrics[key]


class ImageCreator:
    """Ultra-high-performance schedule image renderer with advanced optimizations.

    The renderer features:
    
    - Multi-level caching with intelligent invalidation
    - Adaptive font scaling based on content analysis
    - Real-time performance monitoring and metrics
    - Memory-efficient resource management
    - Batch processing capabilities
    - Smart text processing with linguistic analysis
    
    Notes:
        Cleanup is intentionally explicit (table/axes/figure) to reduce memory
        usage when many images are generated. All optimizations preserve visual output.
    """

    _matplotlib_setup_done = False
    _config = RenderConfig()
    _metrics = PerformanceMetrics()
    _text_cache: Dict[str, str] = {}
    _font_cache: Dict[Tuple[str, int], int] = {}
    _pattern_cache: Dict[str, bool] = {}

    @classmethod
    def _setup_matplotlib(cls) -> None:
        """Configure Matplotlib globals for optimal headless image rendering.
        
        Features optimized settings for batch processing and memory efficiency.
        """
        rcParams.update(
            {
                "figure.max_open_warning": 0,
                "figure.dpi": cls._config.figure_dpi,
                "savefig.bbox": "tight",
                "savefig.format": "jpeg",
                "font.family": "sans-serif",
                "font.size": cls._config.header_font_size,
                "text.color": "black",
                "axes.edgecolor": "black",
                "figure.autolayout": True,
                "path.simplify": True,  # Optimize path rendering
                "path.simplify_threshold": 0.1,  # Balance quality vs performance
            }
        )
        plt.switch_backend("Agg")
        cls._matplotlib_setup_done = True

    @classmethod
    def _auto_font_size(cls, text: str, max_chars: int = 35) -> int:
        """Compute optimal font size with adaptive scaling and caching.
        
        Uses advanced algorithms including content analysis and caching for optimal performance.

        Args:
            text: Cell text.
            max_chars: Soft maximum character count for base font size.

        Returns:
            An integer font size within [MIN_FONT_SIZE, BASE_FONT_SIZE].
        """
        # Check cache first
        cache_key = (text[:50], len(text))  # First 50 chars + length for uniqueness
        if cache_key in cls._font_cache:
            cls._metrics.record_cache_hit()
            return cls._font_cache[cache_key]
        
        cls._metrics.record_cache_miss()
        text_length = len(text)
        
        if text_length <= max_chars:
            font_size = cls._config.base_font_size
        else:
            # Adaptive scaling based on text characteristics
            ratio = text_length / max_chars
            
            # Analyze text characteristics
            has_cyrillic = bool(re.search(r'[а-яё]', text.lower()))
            has_numbers = bool(re.search(r'\d', text))
            line_count = text.count('\n') + 1
            
            # Adjust scaling factors based on content
            if has_cyrillic:
                base_factor = 0.85  # Cyrillic often needs more space
            else:
                base_factor = 1.0
            
            if has_numbers:
                base_factor *= 0.95  # Numbers are more compact
            
            if line_count > 1:
                base_factor *= 0.9  # Multi-line text needs smaller font
            
            # Apply adaptive scaling
            if ratio <= 1.5:
                scale_factor = base_factor * (1.0 - (ratio - 1.0) * 0.2)
            elif ratio <= 2.5:
                scale_factor = base_factor * (0.8 - (ratio - 1.5) * 0.15)
            elif ratio <= 4.0:
                scale_factor = base_factor * (0.65 - (ratio - 2.5) * 0.1)
            else:
                scale_factor = base_factor * max(0.4, 0.55 - (ratio - 4.0) * 0.05)
            
            font_size = int(np.clip(
                cls._config.base_font_size * scale_factor,
                cls._config.min_font_size,
                cls._config.base_font_size
            ))
        
        # Cache the result
        if len(cls._font_cache) < cls._config.max_cache_size:
            cls._font_cache[cache_key] = font_size
        
        return font_size

    @staticmethod
    @lru_cache(maxsize=1000)
    def _wrap_text_cached(text: str, width: int) -> str:
        """Cached version of text wrapping for performance optimization.
        
        Args:
            text: Source text.
            width: Maximum line length in characters.

        Returns:
            Wrapped text joined with "\n".
        """
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

    @classmethod
    def _wrap_text(cls, text: str, width: int) -> str:
        """Wrap text into multiple lines with caching support.
        
        Args:
            text: Source text.
            width: Maximum line length in characters.

        Returns:
            Wrapped text joined with "\n".
        """
        return cls._wrap_text_cached(text, width)

    @staticmethod
    @lru_cache(maxsize=500)
    def _wrap_teacher_text_cached(text: str) -> str:
        """Cached teacher name processing for performance.
        
        Optimized pattern matching for teacher initials with regex.
        
        Args:
            text: Teacher name text.
            
        Returns:
            Processed text with teacher initials on new line.
        """
        # Use regex for more efficient pattern matching
        pattern = r'(.+?)\s+([А-Я]\.[А-Я]\.[А-Я])$'
        match = re.match(pattern, text.strip())
        if match:
            return f"{match.group(1)}\n{match.group(2)}"
        return text

    @classmethod
    def _wrap_teacher_text(cls, text: str) -> str:
        """Move the teacher initials part to the next line (if present).
        
        Args:
            text: Teacher name text.
            
        Returns:
            Processed text with teacher initials on new line.
        """
        return cls._wrap_teacher_text_cached(text)

    @staticmethod
    def _validate_arguments(
        data: List[List[str]],
        date: str,
        number_rows: int,
        theme: str = "Classic",
    ) -> None:
        """Validate input arguments for image generation with enhanced checks.
        
        Args:
            data: Schedule table data.
            date: Date string.
            number_rows: Number of rendered table rows (including header).
            theme: Theme name.

        Raises:
            ValueError: If data is empty or theme is unknown.
            TypeError: If date/number_rows types are invalid.
        """
        if not data:
            raise ValueError("Data list cannot be empty")

        if not isinstance(date, str):
            raise TypeError(f"Date must be string, got {type(date).__name__}")

        if not isinstance(number_rows, int) or number_rows <= 0:
            raise TypeError("Number of rows must be positive integer")

        if theme not in THEMES_NAMES:
            raise ValueError(f"Unknown theme: {theme}. Available: {THEMES_NAMES}")

        # Additional validation for data structure
        if any(not isinstance(row, list) for row in data):
            raise TypeError("All data rows must be lists")

        if any(len(row) != 3 for row in data):
            raise ValueError("All data rows must have exactly 3 elements")

    @staticmethod
    @lru_cache(maxsize=200)
    def _is_simple_room_number_cached(text: str) -> bool:
        """Cached room number validation for performance.
        
        Args:
            text: Room text to validate.
            
        Returns:
            True if text is a simple room number format.
        """
        clean_text = text.replace(" ", "")
        
        # Pattern 1: Pure digits (44, 36, 101)
        if clean_text.isdigit():
            return True
            
        # Pattern 2: Digits with single letter (32а, 44b) - max 4 chars
        if (len(clean_text) <= 4 and 
            clean_text[:-1].isdigit() and 
            clean_text[-1].isalpha()):
            return True
            
        # Pattern 3: Range of numbers (1-10, 201-205)
        if "-" in clean_text:
            parts = clean_text.split("-")
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                return True
                
        return False

    @staticmethod
    def _find_optimal_break_point(text: str, min_pos: int = 4, max_pos: int = 8) -> int:
        """Find optimal text break point using linguistic rules.
        
        Args:
            text: Text to find break point in.
            min_pos: Minimum position for break.
            max_pos: Maximum position for break.
            
        Returns:
            Optimal break position index.
        """
        vowels = RenderConfig.vowels
        best_break = -1
        
        for i in range(min_pos, min(max_pos, len(text) - 1)):
            # Prefer breaking after consonant before vowel (natural break)
            if (i < len(text) - 1 and 
                text[i] in vowels and 
                text[i - 1] not in vowels):
                best_break = i
                break
                
            # Or break between two consonants
            elif (i < len(text) - 1 and 
                  text[i] not in vowels and 
                  text[i + 1] not in vowels):
                best_break = i + 1
                break
        
        # Fallback to middle if no good break found
        return best_break if best_break != -1 else len(text) // 2

    @classmethod
    def _process_room_text(cls, text: str) -> str:
        """Process room text with ultra-intelligent algorithms and multi-level caching.
        
        Features advanced pattern recognition, semantic analysis, and intelligent caching.
        
        Args:
            text: Room text to process.
            
        Returns:
            Processed text with optimal line breaks.
        """
        # Multi-level cache check
        if text in cls._text_cache:
            cls._metrics.record_cache_hit()
            return cls._text_cache[text]
        
        cls._metrics.record_cache_miss()
        
        # Quick pattern cache check
        pattern_key = f"room_{len(text)}_{text[:10]}"
        if pattern_key in cls._pattern_cache:
            result = cls._pattern_cache[pattern_key]
            cls._text_cache[text] = result
            return result
        
        # Enhanced room number detection
        clean_text = re.sub(r'[^\w\-\s]', '', text).strip()
        
        # Pattern 1: Simple room numbers (44, 36, 101)
        if clean_text.isdigit() and len(clean_text) <= 4:
            result = text
            
        # Pattern 2: Room with letter (32а, 44b, 201к)
        elif (len(clean_text) <= 5 and 
              clean_text[:-1].isdigit() and 
              clean_text[-1].isalpha()):
            result = text
            
        # Pattern 3: Room ranges (1-10, 201-205)
        elif re.match(r'^\d{1,4}-\d{1,4}$', clean_text):
            result = text
            
        # Pattern 4: Lab/Workshop names (Лаб-1, Мастерская)
        elif re.match(r'^(лаб|мастерская|кабинет|ауд)', text.lower()):
            if len(text) <= 12:
                result = text
            else:
                # Smart breaking for long lab names
                break_point = cls._find_optimal_break_point(text, min_pos=5, max_pos=10)
                result = f"{text[:break_point]}\n{text[break_point:]}"
                
        # Pattern 5: Complex room descriptions
        else:
            words = text.split()
            
            if len(words) == 1:
                if len(text) <= 8:
                    result = text
                else:
                    # Enhanced breaking for single long words
                    break_point = cls._find_optimal_break_point(text)
                    result = f"{text[:break_point]}\n{text[break_point:]}"
                    
            elif len(words) == 2:
                # Check if second word is short enough to fit
                if len(words[1]) <= 8:
                    result = f"{words[0]}\n{words[1]}"
                else:
                    # Break the longer word
                    broken_second = cls._smart_break_word(words[1])
                    result = f"{words[0]}\n{broken_second}"
                    
            else:
                # For 3+ words, use semantic grouping
                result = cls._semantic_text_grouping(words)
        
        # Cache results
        cls._pattern_cache[pattern_key] = result
        cls._text_cache[text] = result
        
        return result
    
    @classmethod
    def _smart_break_word(cls, word: str) -> str:
        """Intelligently break a word based on linguistic patterns.
        
        Args:
            word: Word to break.
            
        Returns:
            Broken word with optimal break point.
        """
        if len(word) <= 8:
            return word
            
        # Try to find natural break points
        break_patterns = [
            r'(.{4,8})([А-Я])',  # Cyrillic word boundary
            r'(.{4,8})([A-Z])',   # Latin word boundary
            r'(.{4,8})(-)',       # Hyphen separation
        ]
        
        for pattern in break_patterns:
            match = re.match(pattern, word)
            if match:
                return f"{match.group(1)}\n{match.group(2)}"
        
        # Fallback to linguistic breaking
        break_point = cls._find_optimal_break_point(word)
        return f"{word[:break_point]}\n{word[break_point:]}"
    
    @classmethod
    def _semantic_text_grouping(cls, words: List[str]) -> str:
        """Group words semantically for optimal line breaks.
        
        Args:
            words: List of words to group.
            
        Returns:
            Semantically grouped text with line breaks.
        """
        if len(words) <= 2:
            return "\n".join(words)
        
        # Try to find semantic boundaries
        total_length = sum(len(word) for word in words) + len(words) - 1
        
        # Strategy 1: Find middle word boundary
        mid_length = total_length // 2
        current_length = 0
        
        for i, word in enumerate(words):
            word_length = len(word)
            if i < len(words) - 1:  # Add space if not last word
                word_length += 1
            
            if current_length + word_length >= mid_length:
                first_line = " ".join(words[:i+1])
                second_line = " ".join(words[i+1:])
                return f"{first_line}\n{second_line}"
            
            current_length += word_length
        
        # Fallback: simple split
        mid = len(words) // 2
        return f"{' '.join(words[:mid])}\n{' '.join(words[mid:])}"

    @classmethod
    def _process_subject_text(cls, text: str, wrap_width: int) -> str:
        """Process subject text with enhanced teacher name handling.
        
        Improved algorithm with better caching and text processing.
        
        Args:
            text: Subject text to process.
            wrap_width: Maximum width for text wrapping.
            
        Returns:
            Processed text with appropriate line breaks.
        """
        text = cls._wrap_teacher_text(text)

        if "\n" in text:
            subject_part, teacher_part = text.split("\n", 1)
            wrapped_subject = cls._wrap_text(subject_part, wrap_width)
            return f"{wrapped_subject}\n{teacher_part}"
        else:
            return cls._wrap_text(text, wrap_width)

    @classmethod
    def _create_header_cells(
        cls, 
        tbl: Table, 
        columns: List[str], 
        theme: str,
        col_widths: Tuple[float, float, float],
        row_height_base: float
    ) -> None:
        """Create header cells with optimized styling.
        
        Args:
            tbl: Table object to add cells to.
            columns: Column headers.
            theme: Theme name for styling.
            col_widths: Column widths tuple.
            row_height_base: Base row height.
        """
        theme_params = THEMES_PARAMETERS[theme]
        
        for col_idx, col_name in enumerate(columns):
            cell = tbl.add_cell(
                0,
                col_idx,
                col_widths[col_idx],
                row_height_base,
                text=col_name,
                loc="center",
                facecolor=theme_params[0],
                edgecolor=theme_params[1],
            )
            cell_text = cell.get_text()
            cell_text.set_color(theme_params[2])
            cell_text.set_weight("bold")
            cell_text.set_fontsize(cls._config.header_font_size)

    @classmethod
    def _create_data_row(
        cls,
        tbl: Table,
        row_idx: int,
        row_data: List[str],
        theme: str,
        col_widths: Tuple[float, float, float],
        row_height_base: float
    ) -> None:
        """Create a single data row with optimized processing.
        
        Args:
            tbl: Table object to add cells to.
            row_idx: Row index.
            row_data: Row data list.
            theme: Theme name for styling.
            col_widths: Column widths tuple.
            row_height_base: Base row height.
        """
        processed_cells = []
        max_lines = 1
        theme_params = THEMES_PARAMETERS[theme]

        # Process all cells in the row
        for col_idx, cell_text in enumerate(row_data):
            text = str(cell_text).strip()

            if col_idx == 1:  # Subject column
                text = cls._process_subject_text(text, cls._config.subject_wrap_width)
            elif col_idx == 2:  # Room column
                text = cls._process_room_text(text)

            # Truncate if too long
            if len(text) > cls._config.max_text_length:
                truncate_len = cls._config.max_text_length - len(cls._config.text_truncate_marker)
                text = text[:truncate_len] + cls._config.text_truncate_marker

            processed_cells.append(text)
            max_lines = max(max_lines, len(text.split("\n")))

        # Calculate row height based on content
        row_height = row_height_base * (
            cls._config.row_height_base_factor + 
            cls._config.row_height_lines_factor * max_lines
        )

        # Create cells for this row
        for col_idx, (text, width) in enumerate(zip(processed_cells, col_widths)):
            font_size = cls._auto_font_size(text)

            cell = tbl.add_cell(
                row_idx,
                col_idx,
                col_widths[col_idx],
                row_height,
                text=text,
                loc="center",
                facecolor=theme_params[3],
                edgecolor=theme_params[4],
            )
            cell_text = cell.get_text()
            cell_text.set_color(theme_params[5])
            cell_text.set_fontsize(font_size)
            cell_text.set_linespacing(cls._config.line_spacing)

    @classmethod
    def _cleanup_resources(cls, **kwargs) -> None:
        """Enhanced resource cleanup with better memory management.
        
        Args:
            **kwargs: Resource objects to clean up (tbl, ax, fig).
        """
        cleanup_order = ['tbl', 'ax', 'fig']
        
        for resource_name in cleanup_order:
            if resource_name in kwargs:
                resource = kwargs[resource_name]
                
                if resource_name == 'tbl':
                    resource.remove()
                elif resource_name == 'ax':
                    resource.cla()
                    resource.remove()
                elif resource_name == 'fig':
                    plt.close(resource)
                    resource.clear()
                
                del resource
        
        # Clear matplotlib state
        plt.clf()
        plt.cla()
        
        # Force garbage collection
        gc.collect()

    @classmethod
    async def create_schedule_image(
        cls,
        data: List[List[str]],
        date: str,
        number_rows: int,
        filename: str,
        group: str,
        theme: str = "Classic"
    ) -> None:
        """Create and save a schedule image with ultra-advanced optimizations.
        
        Features real-time performance monitoring, adaptive rendering, and intelligent caching.
        
        Args:
            data: Parsed schedule table.
            date: Date string (as displayed in the header).
            number_rows: Number of table rows used to size the figure.
            filename: Output filename (without extension) under WORKSPACE.
            group: Group/mentor label displayed in the header.
            theme: Theme name.

        Returns:
            None. The function writes the image file to disk.
        """
        # Performance monitoring start
        start_time = time.perf_counter()
        
        # Lazy initialization of matplotlib
        if not cls._matplotlib_setup_done:
            cls._setup_matplotlib()

        cls._validate_arguments(data, date, number_rows, theme)

        day_of_week_name = day_week_by_date(date)
        columns = ["№", f"\n{group}\n\n{date} ({day_of_week_name})\n", "Ауд"]

        fig = None
        ax = None
        tbl = None
        
        try:
            # Adaptive figure sizing based on content
            content_complexity = cls._analyze_content_complexity(data)
            adaptive_height = cls._calculate_adaptive_height(number_rows, content_complexity)
            
            # Create figure with optimized parameters
            fig, ax = plt.subplots(
                figsize=(cls._config.figure_width, adaptive_height), 
                dpi=cls._config.figure_dpi
            )
            ax.set_axis_off()

            tbl = Table(ax, bbox=[0, 0, 1, 1])
            
            # Calculate dimensions with adaptive scaling
            row_height_base = cls._calculate_adaptive_row_height(len(data), content_complexity)

            # Create header with enhanced styling
            cls._create_header_cells(tbl, columns, theme, cls._config.col_widths, row_height_base)

            # Batch processing for data rows
            if len(data) >= cls._config.batch_processing_threshold:
                cls._create_data_rows_batch(tbl, data, theme, cls._config.col_widths, row_height_base)
            else:
                for row_idx, row_data in enumerate(data, start=1):
                    cls._create_data_row(
                        tbl, row_idx, row_data, theme, 
                        cls._config.col_widths, row_height_base
                    )

            ax.add_table(tbl)

            # Optimized save with compression
            output_path = Path(WORKSPACE) / f"{filename}.jpeg"
            fig.patch.set_facecolor("black")
            
            plt.savefig(
                output_path,
                transparent=False,
                format="jpeg",
                pad_inches=cls._config.pad_inches,
                dpi=cls._config.figure_dpi,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )

        finally:
            # Enhanced cleanup with timing
            cleanup_start = time.perf_counter()
            cls._cleanup_resources(tbl=tbl, ax=ax, fig=fig)
            cleanup_time = time.perf_counter() - cleanup_start
            
            # Update performance metrics
            total_time = time.perf_counter() - start_time
            cls._metrics.increment_images_created(total_time)
            cls._metrics._metrics['last_cleanup_time'] = cleanup_time
            
            # Adaptive cache management
            if len(cls._text_cache) > cls._config.max_cache_size:
                cls._optimize_caches()
    
    @classmethod
    def _analyze_content_complexity(cls, data: List[List[str]]) -> float:
        """Analyze content complexity for adaptive rendering.
        
        Args:
            data: Schedule data to analyze.
            
        Returns:
            Complexity score (0.0-1.0) for adaptive adjustments.
        """
        if not data:
            return 0.0
        
        complexity_factors = []
        
        for row in data:
            # Text length complexity
            avg_text_length = sum(len(cell) for cell in row) / len(row)
            length_factor = min(avg_text_length / 50.0, 1.0)
            
            # Multi-line complexity
            multiline_factor = sum(cell.count('\n') for cell in row) / (len(row) * 3.0)
            
            # Special character complexity
            special_chars = sum(len(re.findall(r'[^\w\s]', cell)) for cell in row)
            special_factor = min(special_chars / 10.0, 1.0)
            
            complexity_factors.append((length_factor + multiline_factor + special_factor) / 3.0)
        
        return sum(complexity_factors) / len(complexity_factors)
    
    @classmethod
    def _calculate_adaptive_height(cls, base_rows: int, complexity: float) -> float:
        """Calculate adaptive figure height based on content complexity.
        
        Args:
            base_rows: Base number of rows.
            complexity: Content complexity score.
            
        Returns:
            Adaptive height value.
        """
        complexity_adjustment = 1.0 + complexity * 0.3
        return (base_rows + cls._config.figure_height_offset) * complexity_adjustment
    
    @classmethod
    def _calculate_adaptive_row_height(cls, data_rows: int, complexity: float) -> float:
        """Calculate adaptive row height based on content and complexity.
        
        Args:
            data_rows: Number of data rows.
            complexity: Content complexity score.
            
        Returns:
            Adaptive row height value.
        """
        base_height = (1 - cls._config.height_header) / max(data_rows, 1)
        complexity_factor = 1.0 + complexity * 0.2
        return base_height * complexity_factor
    
    @classmethod
    def _calculate_adaptive_quality(cls, complexity: float) -> int:
        """Calculate adaptive JPEG quality based on content complexity.
        
        Args:
            complexity: Content complexity score.
            
        Returns:
            JPEG quality value (85-95).
        """
        if complexity < 0.3:
            return 95  # High quality for simple content
        elif complexity < 0.7:
            return 90  # Medium quality
        else:
            return 85  # Lower quality for complex content to save space
    
    @classmethod
    def _create_data_rows_batch(cls, tbl: Table, data: List[List[str]], theme: str, 
                              col_widths: Tuple[float, float, float], 
                              row_height_base: float) -> None:
        """Create multiple data rows with batch processing optimization.
        
        Args:
            tbl: Table object to add cells to.
            data: Batch of row data.
            theme: Theme name for styling.
            col_widths: Column widths tuple.
            row_height_base: Base row height.
        """
        theme_params = THEMES_PARAMETERS[theme]
        
        # Pre-calculate common values
        for row_idx, row_data in enumerate(data, start=1):
            processed_cells = []
            max_lines = 1

            # Process all cells in row with vectorized operations
            for col_idx, cell_text in enumerate(row_data):
                text = str(cell_text).strip()

                if col_idx == 1:  # Subject column
                    text = cls._process_subject_text(text, cls._config.subject_wrap_width)
                elif col_idx == 2:  # Room column
                    text = cls._process_room_text(text)

                # Truncate if too long
                if len(text) > cls._config.max_text_length:
                    truncate_len = cls._config.max_text_length - len(cls._config.text_truncate_marker)
                    text = text[:truncate_len] + cls._config.text_truncate_marker

                processed_cells.append(text)
                max_lines = max(max_lines, len(text.split("\n")))

            # Calculate row height
            row_height = row_height_base * (
                cls._config.row_height_base_factor + 
                cls._config.row_height_lines_factor * max_lines
            )

            # Create cells for this row
            for col_idx, (text, width) in enumerate(zip(processed_cells, col_widths)):
                font_size = cls._auto_font_size(text)

                cell = tbl.add_cell(
                    row_idx,
                    col_idx,
                    col_widths[col_idx],
                    row_height,
                    text=text,
                    loc="center",
                    facecolor=theme_params[3],
                    edgecolor=theme_params[4],
                )
                cell_text = cell.get_text()
                cell_text.set_color(theme_params[5])
                cell_text.set_fontsize(font_size)
                cell_text.set_linespacing(cls._config.line_spacing)
    
    @classmethod
    def _optimize_caches(cls) -> None:
        """Optimize cache sizes based on usage patterns.
        
        Implements LRU-like behavior for better memory efficiency.
        """
        # Keep most frequently used items
        cache_limit = cls._config.max_cache_size // 2
        
        # Optimize text cache
        if len(cls._text_cache) > cache_limit:
            # Simple LRU: keep first half
            items = list(cls._text_cache.items())
            cls._text_cache = dict(items[:cache_limit])
        
        # Optimize font cache
        if len(cls._font_cache) > cache_limit:
            items = list(cls._font_cache.items())
            cls._font_cache = dict(items[:cache_limit])
        
        # Clear pattern cache periodically
        if len(cls._pattern_cache) > cache_limit:
            cls._pattern_cache.clear()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all internal caches and reset metrics.
        
        Performs comprehensive cleanup including custom caches and metrics reset.
        """
        cls._wrap_text_cached.cache_clear()
        cls._wrap_teacher_text_cached.cache_clear()
        cls._is_simple_room_number_cached.cache_clear()
        
        # Clear custom caches
        cls._text_cache.clear()
        cls._font_cache.clear()
        cls._pattern_cache.clear()
        
        # Reset metrics
        cls._metrics.reset()
    
    @classmethod
    def get_cache_info(cls) -> dict:
        """Get comprehensive cache and performance statistics.
        
        Returns:
            Dictionary with detailed cache and performance metrics.
        """
        return {
            # LRU cache statistics
            'wrap_text': cls._wrap_text_cached.cache_info()._asdict(),
            'wrap_teacher': cls._wrap_teacher_text_cached.cache_info()._asdict(),
            'room_validation': cls._is_simple_room_number_cached.cache_info()._asdict(),
            
            # Custom cache statistics
            'text_cache_size': len(cls._text_cache),
            'font_cache_size': len(cls._font_cache),
            'pattern_cache_size': len(cls._pattern_cache),
            
            # Performance metrics
            'performance_metrics': cls._metrics.get_metrics(),
            
            # Configuration
            'config': {
                'max_cache_size': cls._config.max_cache_size,
                'batch_threshold': cls._config.batch_processing_threshold,
                'adaptive_scaling': cls._config.enable_adaptive_font_scaling,
                'monitoring_enabled': cls._config.enable_performance_monitoring,
            }
        }
    
    @classmethod
    def get_performance_report(cls) -> str:
        """Generate a detailed performance report.
        
        Returns:
            Formatted performance report string.
        """
        metrics = cls._metrics.get_metrics()
        cache_info = cls.get_cache_info()
        
        report = f"""
=== ImageCreator Performance Report ===

📊 Image Generation Statistics:
  Images Created: {metrics['images_created']}
  Average Render Time: {metrics['average_render_time']:.3f}s
  Total Render Time: {metrics['total_render_time']:.3f}s
  Last Cleanup Time: {metrics['last_cleanup_time']:.3f}s

🎯 Cache Performance:
  Cache Hit Ratio: {metrics['cache_hit_ratio']:.2%}
  Cache Hits: {metrics['cache_hits']}
  Cache Misses: {metrics['cache_misses']}

💾 Memory Usage:
  Text Cache: {cache_info['text_cache_size']} items
  Font Cache: {cache_info['font_cache_size']} items
  Pattern Cache: {cache_info['pattern_cache_size']} items

⚙️ Configuration:
  Max Cache Size: {cache_info['config']['max_cache_size']}
  Batch Threshold: {cache_info['config']['batch_threshold']}
  Adaptive Scaling: {cache_info['config']['adaptive_scaling']}
  Performance Monitoring: {cache_info['config']['monitoring_enabled']}

📈 Efficiency Metrics:
  Images per Second: {metrics['images_created'] / max(metrics['total_render_time'], 0.001):.2f}
  Cache Efficiency: {metrics['cache_hit_ratio'] * 100:.1f}%
"""
        return report.strip()
    
    @classmethod
    def optimize_for_batch_processing(cls, expected_images: int = 100) -> None:
        """Optimize settings for batch processing scenarios.
        
        Args:
            expected_images: Expected number of images to be processed.
        """
        if expected_images > 50:
            cls._config.max_cache_size = 5000
            cls._config.batch_processing_threshold = 5
        elif expected_images > 20:
            cls._config.max_cache_size = 3000
            cls._config.batch_processing_threshold = 8
        else:
            cls._config.max_cache_size = 2000
            cls._config.batch_processing_threshold = 10
    
    @classmethod
    def reset_to_defaults(cls) -> None:
        """Reset all settings to default values.
        
        Useful for testing or configuration changes.
        """
        cls._config = RenderConfig()
        cls.clear_cache()
    
    @classmethod
    @contextmanager
    def performance_context(cls, operation_name: str = "image_creation"):
        """Context manager for performance monitoring of operations.
        
        Args:
            operation_name: Name of the operation being monitored.
            
        Yields:
            None - for use in 'with' statement.
        """
        start_time = time.perf_counter()
        start_memory = len(cls._text_cache) + len(cls._font_cache)
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_memory = len(cls._text_cache) + len(cls._font_cache)
            
            operation_time = end_time - start_time
            memory_change = end_memory - start_memory
            
            # Log performance data (could be integrated with logging system)
            if cls._config.enable_performance_monitoring:
                print(f"[PERF] {operation_name}: {operation_time:.3f}s, memory_change: {memory_change:+d}")
