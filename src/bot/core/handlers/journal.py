"""E-journal handlers for MTEC schedule bot.

This module contains handlers for managing electronic journal access: 
credential input, saving and deleting login information, and downloading 
grade journals. Includes scenarios for initial setup, modification, 
and deletion of account credentials.
"""

from typing import Optional

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from core.dependencies import container
from phrases import (
    change_data_text,
    correctly_entered_data_text,
    deleted_user_ejournal_info_text,
    enter_fio_text,
    enter_password_text,
    incorrectly_entered_data_text,
    no_data_text,
)
from services.journal_service import send_ejournal_file
from services.database import UserRepository
from ..fsm.states import EJournalFSM
from .common import cancel_action_handler
from .decorators import event_handler


router = Router()


def register(dp: Dispatcher) -> None:
    """Register e-journal handlers with the dispatcher.
    
    Args:
        dp: The aiogram dispatcher instance.
    """
    dp.include_router(router)


@router.message(Command("journal"), F.chat.type == ChatType.PRIVATE)
@router.message(F.text == "📖 Электронный журнал", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def ejournal_handler(ms: Message, state: FSMContext) -> None:
    """Handle e-journal access requests.
    
    Checks for existing credentials and either sends the journal file
    or prompts for username input.
    
    Args:
        ms: E-journal command message.
        state: FSM context for state management.
    """
    if not ms.from_user:
        return

    user_id = ms.from_user.id

    # Check for existing credentials
    async for session in container.db_manager.get_session():
        user_info: list = await UserRepository.get_user_ejournal_info(session, user_id)

    if user_info:
        await send_ejournal_file(user_id)
    else:
        await container.bot.send_message(user_id, no_data_text, parse_mode="HTML")
        await container.bot.send_message(user_id, enter_fio_text)
        await state.set_state(EJournalFSM.enter_username)


@router.message(EJournalFSM.enter_username, F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False, clear_state=False)
async def ejournal_enter_name(ms: Message, state: FSMContext) -> None:
    """Process username input for e-journal credentials.
    
    Validates username input and transitions to password entry state.
    
    Args:
        ms: Username input message.
        state: FSM context for state management.
    """
    if not isinstance(ms.text, str):
        return

    username = ms.text.strip()

    # Handle exit command
    if username == "/exit":
        await cancel_action_handler(ms, state)
        return

    # Store username and prompt for password
    await state.update_data(username=username)
    await ms.answer(enter_password_text)
    await state.set_state(EJournalFSM.enter_password)


@router.message(EJournalFSM.enter_password, F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False, clear_state=False)
async def ejournal_enter_password(ms: Message, state: FSMContext) -> None:
    """Process password input for e-journal credentials.
    
    Validates password input, saves credentials, and sends journal file.
    
    Args:
        ms: Password input message.
        state: FSM context for state management.
    """
    if not isinstance(ms.text, str) or not ms.from_user:
        return

    password = ms.text.strip()

    # Handle exit command
    if password == "/exit":
        await cancel_action_handler(ms, state)
        return

    # Get stored username
    state_data = await state.get_data()
    username = state_data.get("username")

    user_id = ms.from_user.id

    # Validate credentials
    if not username or not password:
        await ms.answer(incorrectly_entered_data_text, parse_mode="HTML")
        await ms.answer(
            "Введите данные...\n\n<i># Отменить действие можно командой\n/exit</i>",
            parse_mode="HTML",
        )
        await state.set_state(EJournalFSM.enter_username)
        return

    # Save credentials to database
    async for session in container.db_manager.get_session():
        await UserRepository.update_ejournal_info(session, user_id, username, password)

    # Send confirmation and journal file
    await ms.answer(correctly_entered_data_text, parse_mode="HTML")
    await send_ejournal_file(user_id)

    await state.clear()


@router.message(Command("change_journal_info"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def change_ejournal_info_handler(ms: Message, state: FSMContext) -> None:
    """Handle e-journal credential change requests.
    
    Initiates the credential change process by prompting for new username.
    
    Args:
        ms: Change credentials command message.
        state: FSM context for state management.
    """
    await ms.answer(change_data_text, parse_mode="HTML")
    await ms.answer(enter_fio_text)
    await state.set_state(EJournalFSM.enter_username)


@router.message(Command("delete_journal_info"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def delete_ejournal_info_handler(ms: Message, state: FSMContext) -> None:
    """Handle e-journal credential deletion requests.
    
    Removes stored credentials from the database.
    
    Args:
        ms: Delete credentials command message.
        state: FSM context for state management.
    """
    if not ms.from_user:
        return

    user_id = ms.from_user.id

    # Delete credentials from database
    async for session in container.db_manager.get_session():
        await UserRepository.delete_ejournal_info(session, user_id)

    await ms.answer(deleted_user_ejournal_info_text)
