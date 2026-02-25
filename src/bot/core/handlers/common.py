"""Common handlers for MTEC schedule bot user interactions.

This module contains handlers for user registration, status selection (student/mentor),
group changes, additional functions, technical support, and non-text message handling.
"""

from typing import Optional

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config.bot_config import ADMIN
from config.paths import WORKSPACE
from core.dependencies import container
from phrases import (
    base_additionally_text,
    bot_additionally_text,
    change_group_text,
    enter_message_text,
    exit_text,
    legal_information,
    non_text_message_text,
    restart_text,
    select_group_text,
    select_mentor_fio_text,
    select_status_text,
    selected_group_next_text,
    selected_group_text,
    selected_mentor_fio_text,
    sn_additionally_text,
    support_text,
    thx_for_message_text,
    welcome_text,
)
from services.schedule_service import ScheduleService
from utils.markup import (
    inliine_markup_select_status,
    inline_markup_additional_functions,
    inline_markup_additional_functions_bot,
    inline_markup_additional_functions_extended,
    inline_markup_additional_functions_social_networks,
    _inline_markup_select_group,
    reply_markup_additional_functions,
    reply_markup_additional_functions_admin,
)
from services.database import UserRepository
from ..filters.custom_filters import LegalInformationFilter
from ..fsm.states import SelectGroupFSM, SelectMentorNameFSM, SelectStatusFSM, SupportFSM
from .decorators import event_handler


router = Router()
schedule_service = ScheduleService()


def register(dp: Dispatcher) -> None:
    """Register common handlers with the dispatcher.
    
    Args:
        dp: The aiogram dispatcher instance.
    """
    dp.include_router(router)


@router.callback_query(LegalInformationFilter(), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False, clear_state=True)
async def legal_information_callback(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle legal information callback.
    
    Sends legal information text to the user.
    
    Args:
        cb: Callback query from legal information button.
        state: FSM context for state management.
    """
    await container.bot.send_message(cb.from_user.id, legal_information, parse_mode="HTML")


@router.message(
    F.content_type.in_({"photo", "video", "audio", "document", "sticker"}), 
    F.chat.type == ChatType.PRIVATE
)
@event_handler(admin_check=False, clear_state=True)
async def non_text_message_handler(ms: Message, state: FSMContext) -> None:
    """Handle non-text messages.
    
    Responds with a message that only text is supported.
    
    Args:
        ms: Non-text message from user.
        state: FSM context for state management.
    """
    await ms.answer(non_text_message_text)


@router.message(Command("exit"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def cancel_action_handler(ms: Message, state: FSMContext) -> None:
    """Handle exit command to cancel current action.
    
    Sends exit confirmation message and clears state.
    
    Args:
        ms: Exit command message.
        state: FSM context for state management.
    """
    await ms.answer(exit_text)


@router.message(Command("restart"), F.chat.type == ChatType.PRIVATE)
@event_handler(log_event=False, admin_check=False)
async def restart_bot_handler(ms: Message, state: FSMContext) -> None:
    """Handle bot restart command.
    
    Resets bot state and shows main menu with admin options if applicable.
    
    Args:
        ms: Restart command message.
        state: FSM context for state management.
    """
    user_id = ms.from_user.id if ms.from_user else None
    if user_id:
        print(f"{user_id} - Bot restarted")

    # Select appropriate markup based on user role
    markup = reply_markup_additional_functions_admin if user_id == ADMIN else reply_markup_additional_functions

    await ms.answer(restart_text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("start"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def start_handler(ms: Message, state: FSMContext) -> None:
    """Handle start command for new users.
    
    Shows welcome message and prompts for status selection.
    
    Args:
        ms: Start command message.
        state: FSM context for state management.
    """
    message1 = await ms.answer(text=welcome_text)
    message2 = await ms.answer(
        text=select_status_text, 
        reply_markup=inliine_markup_select_status
    )

    await state.update_data(messages_id=[message1.message_id, message2.message_id])
    await state.set_state(SelectStatusFSM.select_status)


@router.callback_query(SelectStatusFSM.select_status)
@event_handler(admin_check=False, clear_state=False)
async def select_status_handler(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle user status selection.
    
    Processes student or mentor selection and prompts for appropriate information.
    
    Args:
        cb: Status selection callback query.
        state: FSM context for state management.
    """
    chat_id = cb.from_user.id
    status = cb.data

    state_data = await state.get_data()
    messages = state_data.get("messages_id", [])

    if status == "👩‍🏫 Преподаватель":
        message3 = await container.bot.send_message(
            chat_id=chat_id, 
            text=select_mentor_fio_text
        )
        messages.append(message3.message_id)
        await state.update_data(messages_id=messages)
        await state.set_state(SelectMentorNameFSM.select_mentor_name)

    elif status == "👨‍🎓 Студент":
        message3 = await container.bot.send_message(
            chat_id=chat_id,
            text=select_group_text,
            reply_markup=_inline_markup_select_group,
        )
        messages.append(message3.message_id)
        await state.update_data(messages_id=messages)
        await state.set_state(SelectGroupFSM.select_group)


@router.message(SelectMentorNameFSM.select_mentor_name)
@event_handler(admin_check=False, clear_state=False)
async def selected_mentor_name_callback(ms: Message, state: FSMContext) -> None:
    """Handle mentor name input.
    
    Processes mentor name registration and sends welcome messages.
    
    Args:
        ms: Message with mentor name.
        state: FSM context for state management.
    """
    if not ms.from_user or not isinstance(ms.text, str):
        return

    user_id = ms.from_user.id
    mentor_name = ms.text.strip()

    # Update user in database
    async for session in container.db_manager.get_session():
        await UserRepository.create_or_update_user(
            session, user_id, "mentor", mentor_name=mentor_name
        )

    # Clean up previous messages
    state_data = await state.get_data()
    messages_to_delete = state_data.get("messages_id", [])
    chat_id = ms.chat.id if ms.chat else user_id

    if messages_to_delete:
        await container.bot.delete_messages(chat_id=chat_id, message_ids=messages_to_delete)

    # Send confirmation and menu
    await container.bot.send_message(
        user_id,
        selected_mentor_fio_text.format(mentor_fio=mentor_name),
        reply_markup=reply_markup_additional_functions,
        parse_mode="HTML",
    )

    await container.bot.send_message(
        user_id,
        selected_group_next_text,
        reply_markup=inline_markup_additional_functions,
    )

    await state.clear()
    await schedule_service.send_mentor_schedule(user_id, mentor_name)


@router.callback_query(SelectGroupFSM.select_group)
@event_handler(admin_check=False, clear_state=False)
async def selected_group_callback(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle group selection.
    
    Processes group selection and sends welcome messages.
    
    Args:
        cb: Group selection callback query.
        state: FSM context for state management.
    """
    user_id = cb.from_user.id
    user_group = cb.data

    if not isinstance(user_group, str):
        return

    # Update user in database
    async for session in container.db_manager.get_session():
        await UserRepository.create_or_update_user(
            session, user_id, "student", student_group=user_group
        )

    # Clean up previous messages
    state_data = await state.get_data()
    messages_to_delete = state_data.get("messages_id", [])
    chat_id = cb.message.chat.id if cb.message else user_id

    if messages_to_delete:
        await container.bot.delete_messages(chat_id=chat_id, message_ids=messages_to_delete)

    # Send confirmation and menu
    await container.bot.send_message(
        user_id,
        selected_group_text.format(user_group=user_group),
        reply_markup=reply_markup_additional_functions,
        parse_mode="HTML",
    )

    await container.bot.send_message(
        user_id,
        selected_group_next_text,
        reply_markup=inline_markup_additional_functions,
    )

    await state.clear()
    await schedule_service.send_schedule_by_group(user_id, user_group)


@router.message(Command("change_group"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def change_group_handler(ms: Message, state: FSMContext) -> None:
    """Handle group change command.
    
    Prompts user to select a new group.
    
    Args:
        ms: Change group command message.
        state: FSM context for state management.
    """
    message = await ms.answer(
        change_group_text, 
        reply_markup=_inline_markup_select_group
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectGroupFSM.select_group)


@router.message(F.text == "🔍 Дополнительно", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def additionally_handler(ms: Message, state: FSMContext) -> None:
    """Handle additional functions menu.
    
    Shows extended menu with additional bot functions.
    
    Args:
        ms: Additional functions menu message.
        state: FSM context for state management.
    """
    await ms.answer(
        base_additionally_text,
        reply_markup=inline_markup_additional_functions_extended,
    )
    await ms.answer(
        sn_additionally_text,
        reply_markup=inline_markup_additional_functions_social_networks,
    )
    await ms.answer(
        bot_additionally_text, 
        reply_markup=inline_markup_additional_functions_bot
    )


@router.message(Command("support"), F.chat.type == ChatType.PRIVATE)
@router.message(F.text == "💬 Помощь")
@event_handler(admin_check=False)
async def technical_support_handler(ms: Message, state: FSMContext) -> None:
    """Handle technical support initiation.
    
    Shows support information and prompts for user message.
    
    Args:
        ms: Support command or help button message.
        state: FSM context for state management.
    """
    message1 = await ms.answer(support_text, parse_mode="HTML")
    message2 = await ms.answer(enter_message_text)

    await state.update_data(need_to_delete=[message1.message_id, message2.message_id])
    await state.set_state(SupportFSM.support)


@router.message(SupportFSM.support)
@event_handler(admin_check=False, clear_state=False)
async def technical_support_next_handler(ms: Message, state: FSMContext) -> None:
    """Handle technical support message submission.
    
    Processes user support message and saves to file.
    
    Args:
        ms: Support message from user.
        state: FSM context for state management.
    """
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    data = await state.get_data()
    messages_to_delete = data.get("need_to_delete", [])

    if not isinstance(messages_to_delete, list) or not ms.from_user:
        return

    user_id = ms.from_user.id
    user_info = {
        'username': ms.from_user.username or "N/A",
        'first_name': ms.from_user.first_name or "N/A",
        'last_name': ms.from_user.last_name or "N/A"
    }

    # Clean up previous messages
    await container.bot.delete_messages(user_id, messages_to_delete)
    await state.update_data(need_to_delete=[])

    await ms.answer(thx_for_message_text)

    # Save support message to file
    try:
        with open(f"{WORKSPACE}support.txt", "a", encoding="utf-8") as file:
            file.write(
                f"📋 Новое сообщение в тех. поддержку от @{user_info['username']} - "
                f"{user_info['first_name']} - {user_info['last_name']} - {user_id}:\n"
                f"{ms.text}\n\n"
            )
    except Exception as e:
        print(f"Failed to save support message: {e}")

    await state.clear()
