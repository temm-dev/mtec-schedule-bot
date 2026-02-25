"""Chat handlers for MTEC schedule bot group management.

This module contains handlers for bot operations in group chats: bot addition,
subscription setup for groups or mentors, settings reset, and schedule requests.
Includes admin rights verification for configuration operations.
"""

from functools import wraps
from typing import Optional

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from core.dependencies import container
from phrases import group_welcome_text
from services.schedule_service import ScheduleService
from utils.markup import _inline_markup_select_group, _inline_markup_select_mentors_fcs, _mentors_dict
from services.database import ChatRepository
from ..fsm.states import ChatSelectGroupFSM, ChatSelectMentorNameFSM


router = Router()
private_router = Router()


def register(dp: Dispatcher) -> None:
    """Register chat handlers with the dispatcher.
    
    Args:
        dp: The aiogram dispatcher instance.
    """
    dp.include_router(router)


def admin_required():
    """Decorator to restrict handler access to chat administrators only.
    
    Returns:
        Decorator function that checks admin permissions.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            try:
                chat_id = event.chat.id
            except AttributeError:
                chat_id = event.message.chat.id

            # Check if user is admin
            if event.from_user.id != chat_id:
                try:
                    member = await event.bot.get_chat_member(chat_id, event.from_user.id)
                    if member.status not in ["administrator", "creator"]:
                        await event.reply("❌ Настраивать бота могут только администраторы группы")
                        return
                except Exception as e:
                    print(f"Admin check failed: {e}")
                    await event.reply("⚠️ Не удалось проверить права. Убедитесь, что бот - администратор группы.")
                    return

            return await func(event, *args, **kwargs)
        return wrapper
    return decorator


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated) -> None:
    """Handle bot addition to group chat.
    
    Sends welcome message and creates chat record in database.
    
    Args:
        event: Chat member update event.
    """
    chat = event.chat

    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        try:
            await container.bot.send_message(
                chat_id=chat.id, 
                text=group_welcome_text, 
                parse_mode=ParseMode.HTML
            )

            async for session in container.db_manager.get_session():
                await ChatRepository.create_or_update_chat(session, chat.id)

        except Exception as e:
            print(f"Error handling bot addition to group: {e}")


@router.message(Command("setup_group"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
@admin_required()
async def cmd_setup_group(message: Message, state: FSMContext) -> None:
    """Handle group subscription setup command.
    
    Prompts admin to select a group for schedule subscription.
    
    Args:
        message: Command message.
        state: FSM context for state management.
    """
    await message.reply(
        "👥 Выберите необходимую группу:", 
        reply_markup=_inline_markup_select_group
    )
    await state.set_state(ChatSelectGroupFSM.select_group)


@router.message(Command("setup_mentor"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
@admin_required()
async def cmd_setup_mentor(message: Message, state: FSMContext) -> None:
    """Handle mentor subscription setup command.
    
    Prompts admin to select a mentor for schedule subscription.
    
    Args:
        message: Command message.
        state: FSM context for state management.
    """
    await message.reply(
        "👩‍🏫 Выберите необходимого преподавателя:", 
        reply_markup=_inline_markup_select_mentors_fcs
    )
    await state.set_state(ChatSelectMentorNameFSM.select_mentor_name)


@router.message(Command("reset"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
@admin_required()
async def cmd_reset(message: Message, state: FSMContext) -> None:
    """Handle settings reset command.
    
    Resets all chat subscriptions and clears FSM state.
    
    Args:
        message: Command message.
        state: FSM context for state management.
    """
    chat_id = message.chat.id

    await message.reply("⚙️ Настройки сброшены!")

    async for session in container.db_manager.get_session():
        await ChatRepository.unsubscribe(session, chat_id)

    await state.clear()


@router.message(Command("schedule"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def cmd_schedule(message: Message, state: FSMContext) -> None:
    """Handle schedule request command.
    
    Sends schedule based on current chat subscription (group or mentor).
    
    Args:
        message: Command message.
        state: FSM context for state management.
    """
    chat_id = message.chat.id

    async for session in container.db_manager.get_session():
        chat_info = await ChatRepository.get_chat_subscription_info(session, chat_id)

    if len(chat_info) == 1:
        return

    chat_id = chat_info["chat_id"]
    sub_group = chat_info["subscribed_to_group"]
    sub_mentor = chat_info["subscribed_to_mentor"]

    if sub_group:
        schedule_service = ScheduleService()
        await schedule_service.send_schedule_by_group(chat_id, sub_group, "_chat_schedule")

    if sub_mentor:
        schedule_service = ScheduleService()
        await schedule_service.send_mentor_schedule(chat_id, sub_mentor, "_chat_schedule")

    await state.clear()


@router.message(Command("settings"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    """Handle settings display command.
    
    Shows current subscription settings for the chat.
    
    Args:
        message: Command message.
        state: FSM context for state management.
    """
    chat_id = message.chat.id

    async for session in container.db_manager.get_session():
        chat_info = await ChatRepository.get_chat_subscription_info(session, chat_id)

    sub_group = chat_info.get("subscribed_to_group", "Не установлено")
    sub_mentor = chat_info.get("subscribed_to_mentor", "Не установлено")

    await message.reply(
        f"<b>⚙️ Настройки бота:</b>\n\n"
        f"👥 Выбрана группа: <b>{sub_group}</b>\n"
        f"👩‍🏫 Выбран преподаватель: <b>{sub_mentor}</b>",
        parse_mode=ParseMode.HTML,
    )

    await state.clear()


@router.callback_query(StateFilter(ChatSelectGroupFSM.select_group))
@admin_required()
async def selected_group_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle group selection from inline keyboard.
    
    Updates chat subscription with selected group.
    
    Args:
        callback_query: Callback query from inline keyboard.
        state: FSM context for state management.
    """
    chat_id = callback_query.message.chat.id
    selected_group = callback_query.data

    await callback_query.answer(f"✅ Выбрана группа: {selected_group}")
    await callback_query.message.edit_text(
        f"👥 Выбрана группа: <b>{selected_group}</b>", 
        parse_mode=ParseMode.HTML
    )

    async for session in container.db_manager.get_session():
        await ChatRepository.subscribe_to_group(session, chat_id, selected_group)

    await state.clear()


@router.callback_query(StateFilter(ChatSelectMentorNameFSM.select_mentor_name))
@admin_required()
async def selected_mentor_name_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle mentor selection from inline keyboard.
    
    Updates chat subscription with selected mentor.
    
    Args:
        callback_query: Callback query from inline keyboard.
        state: FSM context for state management.
    """
    chat_id = callback_query.message.chat.id
    mentor_key = callback_query.data
    
    selected_mentor = _mentors_dict.get(mentor_key, "Неизвестный преподаватель")
    
    await callback_query.answer(f"✅ Выбран преподаватель: {selected_mentor}")
    await callback_query.message.edit_text(
        f"👩‍🏫 Выбран преподаватель: <b>{selected_mentor}</b>", 
        parse_mode=ParseMode.HTML
    )

    async for session in container.db_manager.get_session():
        await ChatRepository.subscribe_to_mentor(session, chat_id, selected_mentor)

    await state.clear()
