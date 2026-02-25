"""
log.py - User action logging utilities

Contains functions for logging user actions (messages and callback queries)
to a file for analysis and debugging. Logs include user ID, username,
first name, last name, and message text or callback data.
"""

import logging
from datetime import datetime
from typing import Any, Union
from pathlib import Path

from aiogram.types import Message, CallbackQuery
from config.paths import WORKSPACE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
LOG_FILE = Path(WORKSPACE) / "logs.txt"
LOG_FORMAT = "{timestamp} | {user_id} | @{username} | {first_name} {last_name} | {action_type} | {details}\n"


async def print_sent(user_id: int) -> None:
    """Print a success message when a message is sent to a user.
    
    Args:
        user_id: The ID of the user who received the message.
    """
    try:
        print(f"\t\t🟩 {user_id} | Message sent")
    except Exception as e:
        logger.error(f"Error in print_sent for user {user_id}: {e}")


async def log(data: Union[Message, CallbackQuery], log_type: str = "message") -> None:
    """Log user actions to a file with detailed information.
    
    Args:
        data: The message or callback query object from aiogram.
        log_type: Type of the log entry, either "message" or "callback".
        
    Raises:
        ValueError: If an unsupported log_type is provided.
        IOError: If there's an error writing to the log file.
    """
    if log_type not in ("message", "callback"):
        raise ValueError(f"Unsupported log type: {log_type}")
    
    try:
        # Extract user information safely
        user = data.from_user
        user_id = getattr(user, 'id', 'N/A')
        username = getattr(user, 'username', 'N/A')
        first_name = getattr(user, 'first_name', 'N/A')
        last_name = getattr(user, 'last_name', 'N/A')
        
        # Get the appropriate data based on log type
        if log_type == "message":
            details = getattr(data, 'text', 'No text content')
        else:  # callback
            details = getattr(data, 'data', 'No callback data')
        
        # Format the log entry
        log_entry = LOG_FORMAT.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            action_type=log_type.upper(),
            details=details
        )
        
        # Write to log file
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as log_file:
                log_file.write(log_entry)
        except IOError as e:
            logger.error(f"Failed to write to log file: {e}")
            raise
            
    except AttributeError as e:
        logger.error(f"Invalid data structure received: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in log function: {e}")


async def log_message(message: Message) -> None:
    """Log a user message.
    
    Args:
        message: The message object from aiogram.
    """
    await log(message, "message")


async def log_callback(callback_query: CallbackQuery) -> None:
    """Log a callback query.
    
    Args:
        callback_query: The callback query object from aiogram.
    """
    await log(callback_query, "callback")


async def get_recent_logs(limit: int = 50) -> list[str]:
    """Retrieve recent log entries.
    
    Args:
        limit: Maximum number of log entries to return.
        
    Returns:
        List of recent log entries, most recent first.
        
    Raises:
        IOError: If there's an error reading the log file.
    """
    try:
        if not LOG_FILE.exists():
            return ["No log file found"]
            
        with open(LOG_FILE, "r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
            return lines[-limit:] if limit > 0 else lines
    except IOError as e:
        logger.error(f"Error reading log file: {e}")
        raise