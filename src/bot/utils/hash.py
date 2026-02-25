"""
hash.py - Utilities for data hashing

Contains functions for generating hashes based on schedule data.
Used to track changes in schedules by comparing hashes.
Includes text normalization (accent removal, Unicode normalization) before hashing.
"""

import hashlib
import html
import re
import unicodedata
from typing import List


async def generate_hash(schedule: List[List[str]], remove_accents: bool = True) -> str:
    """Generate a SHA-256 hash for the given schedule data.

    This function creates a deterministic hash from schedule data by normalizing
    the text content and then applying SHA-256 hashing. The normalization process
    includes HTML entity decoding, Unicode normalization, optional accent removal,
    case folding, and whitespace normalization.

    Args:
        schedule: A 2D list representing schedule data where each inner list
            contains string values for a row/entry in the schedule.
        remove_accents: If True, removes diacritical marks from text during
            normalization. Defaults to True.

    Returns:
        A 64-character hexadecimal string representing the SHA-256 hash of the
        normalized schedule data.

    Raises:
        TypeError: If schedule is not a list or contains non-list elements.
        ValueError: If schedule contains non-string values that cannot be
            normalized.

    Examples:
        >>> schedule = [["Math", "9:00"], ["Physics", "10:30"]]
        >>> hash_value = await generate_hash(schedule)
        >>> isinstance(hash_value, str)
        True
        >>> len(hash_value)
        64
    """
    if not isinstance(schedule, list):
        raise TypeError("Schedule must be a list of lists")
    
    # Pre-compile regex patterns for better performance
    zero_width_pattern = re.compile(r"[\u200B-\u200F\uFEFF]")
    whitespace_pattern = re.compile(r"\s+")
    
    def normalize_text(text: str) -> str:
        """Normalize text content for consistent hashing.

        Performs HTML entity decoding, Unicode normalization, optional accent
        removal, case folding, and whitespace normalization.

        Args:
            text: The input string to normalize.

        Returns:
            Normalized string suitable for consistent hashing.

        Raises:
            ValueError: If the input cannot be properly normalized.
        """
        try:
            # Handle None values and decode HTML entities
            if text is None:
                text = ""
            text = html.unescape(text)
            
            # Unicode normalization (NFKC for compatibility)
            text = unicodedata.normalize("NFKC", text)
            
            # Replace zero-width characters with spaces
            text = zero_width_pattern.sub(" ", text)
            
            # Remove accents if requested
            if remove_accents:
                text = unicodedata.normalize("NFD", text)
                # Remove combining characters (diacritical marks)
                text = "".join(ch for ch in text if not unicodedata.combining(ch))
                text = unicodedata.normalize("NFC", text)
            
            # Case folding for case-insensitive comparison
            text = text.casefold()
            
            # Normalize whitespace
            text = whitespace_pattern.sub(" ", text).strip()
            
            return text
            
        except (UnicodeError, ValueError) as e:
            raise ValueError(f"Failed to normalize text '{text}': {e}") from e
    
    try:
        # Use a more efficient separator
        separator = "\x1f"  # Unit separator, unlikely to appear in schedule data
        normalized_parts = []
        
        # Process schedule rows with memory efficiency
        for row_index, row in enumerate(schedule):
            if not isinstance(row, list):
                raise TypeError(f"Row {row_index} is not a list")
            
            # Normalize each cell in the row
            try:
                normalized_cells = [normalize_text(str(cell)) for cell in row]
                normalized_parts.append(separator.join(normalized_cells))
            except ValueError as e:
                raise ValueError(f"Error in row {row_index}: {e}") from e
        
        # Create canonical representation
        canonical_text = separator.join(normalized_parts)
        
        # Generate SHA-256 hash
        hash_object = hashlib.sha256(canonical_text.encode("utf-8"))
        return hash_object.hexdigest()
        
    except MemoryError:
        # Handle potential memory issues with large schedules
        raise MemoryError("Schedule too large to process for hashing") from None
    except Exception as e:
        # Catch any other unexpected errors
        if isinstance(e, (TypeError, ValueError, MemoryError)):
            raise
        raise RuntimeError(f"Unexpected error during hash generation: {e}") from e
