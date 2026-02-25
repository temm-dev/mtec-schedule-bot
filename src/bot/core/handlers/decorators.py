"""Event handler decorators for MTEC schedule bot.

This module contains decorators for bot event processing with logging functions,
administrator rights checking, FSM state management, and exception handling.
The main decorator @event_handler is used to standardize message and callback
query processing.
"""

from functools import wraps
from typing import Union, Optional, Callable, Any

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from config.bot_config import ADMIN
from utils.formatters import format_error_message
from utils.log import log


def event_handler(
    log_event: bool = True, 
    clear_state: bool = True, 
    admin_check: bool = True
) -> Callable:
    """Decorator for standardized event handling with logging and validation.
    
    Provides consistent handling for bot events including:
    - Event logging for debugging and monitoring
    - Administrator rights validation
    - FSM state management
    - Exception handling with proper error formatting
    
    Args:
        log_event: Whether to log the event (default: True)
        clear_state: Whether to clear FSM state before processing (default: True)
        admin_check: Whether to validate admin rights (default: True)
        
    Returns:
        Decorated function with enhanced error handling and validation.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            event: Union[Message, CallbackQuery], 
            state: FSMContext, 
            *args, 
            **kwargs
        ) -> Optional[Any]:
            try:
                # Log event if enabled
                if log_event:
                    if isinstance(event, Message):
                        await log(event)
                    elif isinstance(event, CallbackQuery):
                        await log(event.message)

                # Check admin rights if enabled
                if admin_check and _is_admin_required(event):
                    if isinstance(event, CallbackQuery):
                        await event.answer("⛔ Доступ запрещен!", show_alert=True)
                    return None

                # Clear FSM state if enabled
                if clear_state:
                    await _clear_state_if_set(state)

                return await func(event, state, *args, **kwargs)

            except Exception as e:
                error_msg = format_error_message(func.__name__, e)
                print(error_msg)
                
                # Optionally send error to user for debugging
                if isinstance(event, Message) and event.from_user:
                    try:
                        await event.answer("⚠️ An error occurred. Please try again later.")
                    except Exception:
                        pass  # Avoid infinite error loops
                        
                return None

        return wrapper
    return decorator


def _is_admin_required(event: Union[Message, CallbackQuery]) -> bool:
    """Check if admin rights validation is required and user is not admin.
    
    Args:
        event: The event to check.
        
    Returns:
        True if admin check is required and user is not admin.
    """
    return (
        event.from_user is not None 
        and event.from_user.id != ADMIN
    )


async def _clear_state_if_set(state: FSMContext) -> None:
    """Clear FSM state if it's currently set.
    
    Args:
        state: The FSM context to clear.
    """
    try:
        current_state = await state.get_state()
        if current_state:
            await state.clear()
    except Exception:
        # Ignore state clearing errors to avoid breaking main flow
        pass
