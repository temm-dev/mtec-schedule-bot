"""
Message formatting utilities for error reporting.

This module provides functions for formatting text messages, particularly for
creating structured error messages with borders and headers in a consistent format.
"""

from typing import Optional, TypeVar, Union
from dataclasses import dataclass

# Type variable for error types
ErrorType = TypeVar('ErrorType', bound=Exception)

@dataclass
class ErrorMessage:
    """Represents a formatted error message with header and border styling."""
    header: str
    error: Union[Exception, str]
    padding: int = 16
    border_char: str = "-"
    corner_char: str = "!"

    def __post_init__(self) -> None:
        """Validate initialization parameters."""
        if not isinstance(self.padding, int) or self.padding < 0:
            raise ValueError("Padding must be a non-negative integer")
        if not all(isinstance(char, str) and len(char) == 1 
                  for char in (self.border_char, self.corner_char)):
            raise ValueError("Border and corner characters must be single characters")

    def format(self) -> str:
        """Format the error message with borders and header.
        
        Returns:
            str: Formatted error message with borders and header.
        """
        # Convert error to string safely
        error_str = str(self.error) if self.error else "Unknown error"
        
        # Calculate frame width based on the longest line
        content_width = max(
            len(self.header) + 4,  # +4 for " | " and space
            len(error_str),
            20  # Minimum width
        )
        
        # Create top and bottom border
        border = self.corner_char + self.border_char * (content_width + 2) + self.corner_char
        # Create header line with padding
        header_line = " " * self.padding + f"| {self.header} |" + " " * self.padding
        
        return f"\n{border}\n{header_line}\n{error_str}\n{border}\n"


def format_error_message(
    function_name: str, 
    error: Union[Exception, str], 
    padding: int = 16
) -> str:
    """Create a formatted error message with borders and function name header.
    
    Args:
        function_name: Name of the function where the error occurred.
        error: The error/exception object or error message string.
        padding: Number of spaces to pad the header with (default: 16).
        
    Returns:
        str: Formatted error message with borders and function name.
        
    Example:
        >>> try:
        ...     1/0
        ... except Exception as e:
        ...     print(format_error_message("test_function", e))
        !----------------------!
                | test_function |                
        division by zero
        !----------------------!
    """
    return ErrorMessage(
        header=function_name,
        error=error,
        padding=padding
    ).format()


def format_warning(message: str, padding: int = 16) -> str:
    """Create a formatted warning message with borders.
    
    Args:
        message: Warning message to display.
        padding: Number of spaces to pad the header with (default: 16).
        
    Returns:
        str: Formatted warning message with borders.
    """
    return ErrorMessage(
        header="WARNING",
        error=message,
        padding=padding,
        border_char="~",
        corner_char="*"
    ).format()