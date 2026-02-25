"""Keyboard utilities for MTEC schedule bot.

This module contains utility functions for building Telegram inline keyboards:
- Multi-column keyboards for group/mentor selection
- Dynamic user settings keyboards
- Keyboard layout optimization for better UX
"""

from typing import List, Dict, Any
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config.settings import SETTINGS_DICT_TEXT


def build_multi_column_keyboard(
    items: List[str], 
    columns: int = 3
) -> List[List[InlineKeyboardButton]]:
    """Create inline keyboard with items arranged in multiple columns.
    
    Args:
        items: List of button text strings.
        columns: Number of columns per row (default: 3).
        
    Returns:
        List of keyboard rows, each containing InlineKeyboardButton objects.
        
    Example:
        >>> buttons = build_multi_column_keyboard(["A", "B", "C", "D"], 2)
        >>> # Returns: [[Button("A"), Button("B")], [Button("C"), Button("D")]]
    """
    if not items:
        return []
    
    if columns <= 0:
        raise ValueError("Columns must be a positive integer")
    
    keyboard_rows = []
    current_row = []
    
    for index, item in enumerate(items, start=1):
        current_row.append(
            InlineKeyboardButton(text=item, callback_data=item)
        )
        
        if index % columns == 0:
            keyboard_rows.append(current_row)
            current_row = []
    
    if current_row:
        keyboard_rows.append(current_row)
        
    return keyboard_rows


def build_settings_keyboard(user_settings: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Build dynamic settings keyboard based on user preferences.
    
    Creates toggle buttons for each user setting with appropriate status indicators.
    Settings are displayed with enabled/disabled state based on current values.
    
    Args:
        user_settings: Dictionary mapping setting names to their boolean values.
        
    Returns:
        InlineKeyboardMarkup with settings buttons and style selection button.
        
    Example:
        >>> settings = {"toggle_schedule": True, "all_semesters": False}
        >>> keyboard = build_settings_keyboard(settings)
    """
    if not isinstance(user_settings, dict):
        raise ValueError("User settings must be a dictionary")
    
    buttons = []
    
    # Create buttons for each setting
    for setting, value in user_settings.items():
        setting_texts = SETTINGS_DICT_TEXT.get(setting)
        if setting_texts:
            # Ensure value is boolean and within valid range
            bool_value = bool(value)
            button_text = setting_texts[int(bool_value)]  # False=0, True=1
            buttons.append([InlineKeyboardButton(
                text=button_text, 
                callback_data=setting
            )])
    
    # Add style selection button at the beginning
    style_button = [InlineKeyboardButton(
        text="🌌 Стиль расписания", 
        callback_data="🌌 Стиль расписания"
    )]
    buttons.insert(0, style_button)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_back_button(text: str = "🔙 Назад") -> InlineKeyboardMarkup:
    """Create a simple back button for navigation.
    
    Args:
        text: Button text (default: "🔙 Назад").
        
    Returns:
        InlineKeyboardMarkup with a single back button.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="back")]]
    )


def create_confirmation_keyboard(
    confirm_text: str = "✅ Да", 
    cancel_text: str = "❌ Отмена",
    confirm_callback: str = "confirm",
    cancel_callback: str = "cancel"
) -> InlineKeyboardMarkup:
    """Create a confirmation keyboard with Yes/No options.
    
    Args:
        confirm_text: Text for confirmation button.
        cancel_text: Text for cancellation button.
        confirm_callback: Callback data for confirmation.
        cancel_callback: Callback data for cancellation.
        
    Returns:
        InlineKeyboardMarkup with confirmation buttons.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
            InlineKeyboardButton(text=cancel_text, callback_data=cancel_callback)
        ]]
    )