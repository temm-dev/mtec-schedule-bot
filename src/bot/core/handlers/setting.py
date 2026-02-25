"""Settings handlers for MTEC schedule bot user preferences.

This module contains handlers for managing user settings: theme selection,
schedule notifications, semester display, and other bot preferences.
Provides interactive interface for settings management with inline buttons.
"""

from aiogram import Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters import Command
from aiogram.enums import ChatType

from config.settings import SETTINGS_DICT_TEXT
from config.themes import THEMES_NAMES
from core.dependencies import container
from phrases import change_theme_text, selected_theme_text, settings_help_text, settings_text
from utils.keyboard import build_settings_keyboard
from utils.markup import inline_markup_select_theme, get_media_photo_themes
from services.database import UserRepository
from ..filters.custom_filters import ScheduleStyle, SettingsFilter
from ..fsm.states import ChangeSettingsFSM, SelectThemeFSM
from .decorators import event_handler


router = Router()


def register(dp: Dispatcher) -> None:
    """Register settings handlers with the dispatcher.
    
    Args:
        dp: The aiogram dispatcher instance.
    """
    dp.include_router(router)


@router.callback_query(ScheduleStyle())
@event_handler(admin_check=False)
async def select_theme_handler(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle theme selection initiation.
    
    Shows theme selection with preview images and current theme info.
    
    Args:
        cb: Theme selection callback query.
        state: FSM context for state management.
    """
    if not cb.from_user:
        return

    user_id = cb.from_user.id

    # Get current user theme
    async for session in container.db_manager.get_session():
        user_theme = await UserRepository.get_user_theme(session, user_id)

    # Send theme preview images
    media_group = get_media_photo_themes()
    if media_group:
        try:
            await container.bot.send_media_group(user_id, media_group)
        except Exception as e:
            print(f"Failed to send theme preview: {e}")

    # Send theme selection message
    await container.bot.send_message(
        user_id,
        change_theme_text.format(user_theme=user_theme),
        reply_markup=inline_markup_select_theme,
        parse_mode="HTML",
    )

    await state.set_state(SelectThemeFSM.select_theme)


@router.callback_query(SelectThemeFSM.select_theme)
@event_handler(admin_check=False, clear_state=False)
async def select_theme_callback(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle theme selection callback.
    
    Processes theme selection and updates user preferences.
    
    Args:
        cb: Theme selection callback query.
        state: FSM context for state management.
    """
    if not cb.from_user or not cb.data:
        return

    user_id = cb.from_user.id
    selected_theme = cb.data

    # Validate theme selection
    if selected_theme not in THEMES_NAMES:
        print(f"Invalid theme selected: {selected_theme}")
        return

    # Update user theme in database
    async for session in container.db_manager.get_session():
        await UserRepository.update_user_theme(session, user_id, selected_theme)

    # Clean up previous messages
    state_data = await state.get_data()
    messages_to_delete = state_data.get("need_to_delete", [])

    try:
        if messages_to_delete:
            await container.bot.delete_messages(user_id, messages_to_delete)
        
        # Delete the original message if it exists
        if cb.message:
            await cb.message.delete()
    except Exception as e:
        print(f"Failed to clean up messages: {e}")

    # Send confirmation
    await container.bot.send_message(
        user_id,
        selected_theme_text.format(user_theme=selected_theme),
        parse_mode="HTML",
    )

    await state.clear()

@router.message(Command("settings"), F.chat.type == ChatType.PRIVATE)
@router.callback_query(SettingsFilter())
@event_handler(admin_check=False)
async def settings_handler(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle settings menu display.
    
    Shows current user settings with interactive toggle buttons.
    
    Args:
        cb: Settings menu callback query.
        state: FSM context for state management.
    """
    if not cb.from_user:
        return

    user_id = cb.from_user.id

    # Get current user settings
    async for session in container.db_manager.get_session():
        user_settings = await UserRepository.get_user_settings(session, user_id)

    # Build settings keyboard
    keyboard = build_settings_keyboard(user_settings)

    # Send settings menu
    await container.bot.send_message(user_id, settings_text)
    sent_message = await container.bot.send_message(
        user_id, 
        settings_help_text, 
        parse_mode="HTML", 
        reply_markup=keyboard
    )

    await state.update_data(message_id=sent_message.message_id)
    await state.set_state(ChangeSettingsFSM.change)


@router.callback_query(ChangeSettingsFSM.change)
@event_handler(admin_check=False, clear_state=False)
async def change_settings(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle individual setting changes.
    
    Processes toggle actions for user settings and updates interface.
    
    Args:
        cb: Setting change callback query.
        state: FSM context for state management.
    """
    if not cb.from_user or not cb.data:
        return

    user_action = cb.data

    # Validate setting action
    if user_action not in SETTINGS_DICT_TEXT:
        print(f"Invalid setting action: {user_action}")
        return

    user_id = cb.from_user.id

    # Get current settings and message ID
    async for session in container.db_manager.get_session():
        user_settings = await UserRepository.get_user_settings(session, user_id)

    state_data = await state.get_data()
    message_id = state_data.get("message_id")

    if not message_id:
        print("No message ID found in state")
        return

    # Get current value and toggle it
    current_value = user_settings.get(user_action, False)
    new_value = not current_value

    # Update setting in database
    async for session in container.db_manager.get_session():
        await UserRepository.update_user_setting(session, user_id, user_action, new_value)

    # Refresh settings display
    async for session in container.db_manager.get_session():
        updated_settings = await UserRepository.get_user_settings(session, user_id)

    keyboard = build_settings_keyboard(updated_settings)

    chat_id = cb.message.chat.id if cb.message else user_id

    try:
        await container.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=settings_help_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        print(f"Failed to update settings message: {e}")
        # Send new message if edit fails
        await container.bot.send_message(
            user_id,
            settings_help_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
