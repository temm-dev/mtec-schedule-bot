"""Schedule handlers for MTEC schedule bot.

This module contains handlers for schedule operations: resend schedule, 
call schedule, mentor schedule, and group schedule viewing.
Includes scenarios for both students and mentors, as well as functions 
for viewing schedules of other groups/mentors.
"""

from typing import Optional

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.dependencies import container
from phrases import (
    checking_schedule_text,
    choosen_schedule_group_text,
    choosen_schedule_mentor_text,
    schedule_group_text,
    schedule_mentor_text,
)
from services.schedule_service import ScheduleService
from utils.markup import (
    _inline_markup_select_group,
    _inline_markup_select_mentors_fcs,
    get_media_call_schedule_photos,
    _mentors_dict,
)
from services.database import UserRepository
from ..fsm.states import SelectGroupScheduleFSM, SelectMentorScheduleFSM
from .decorators import event_handler


router = Router()
schedule_service = ScheduleService()


def register(dp: Dispatcher) -> None:
    """Register schedule handlers with the dispatcher.
    
    Args:
        dp: The aiogram dispatcher instance.
    """
    dp.include_router(router)


@router.message(Command("schedule"), F.chat.type == ChatType.PRIVATE)
@router.message(F.text == "📚 Моё расписание", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def resend_schedule_handler(ms: Message, state: FSMContext) -> None:
    """Handle schedule resend requests.
    
    Sends user's current schedule based on their status (student/mentor).
    
    Args:
        ms: Resend schedule command message.
        state: FSM context for state management.
    """
    if not ms.from_user:
        return

    user_id = ms.from_user.id
    await ms.answer(checking_schedule_text)

    # Get user status and send appropriate schedule
    async for session in container.db_manager.get_session():
        user_status = await UserRepository.get_user_status(session, user_id)

    if user_status == "mentor":
        async for session in container.db_manager.get_session():
            mentor_name = await UserRepository.get_mentor_name_by_id(session, user_id)
            if mentor_name:
                await schedule_service.send_mentor_schedule(user_id, mentor_name, "_resend")
                await container.bot.delete_message(user_id, ms.message_id)
    elif user_status == "student":
        async for session in container.db_manager.get_session():
            user_group = await UserRepository.get_user_group(session, user_id)
            if user_group:
                await schedule_service.send_schedule_by_group(user_id, user_group, "_resend")
                await container.bot.delete_message(user_id, ms.message_id)


@router.message(F.text == "🕒 Расписание звонков", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def send_call_schedule_handler(ms: Message, state: FSMContext) -> None:
    """Handle call schedule requests.
    
    Sends call schedule with media group of photos.
    
    Args:
        ms: Call schedule command message.
        state: FSM context for state management.
    """
    try:
        await ms.answer_media_group(get_media_call_schedule_photos())
    except Exception as e:
        print(f"Failed to send call schedule: {e}")

@router.message(Command("mentor_schedule"), F.chat.type == ChatType.PRIVATE)
@router.message(F.text == "👩‍🏫 Расписание преподавателя", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def schedule_mentor_handler(ms: Message, state: FSMContext) -> None:
    """Handle mentor schedule initiation.
    
    Shows mentor selection interface for schedule viewing.
    
    Args:
        ms: Mentor schedule command message.
        state: FSM context for state management.
    """
    if not ms.from_user:
        return

    message = await ms.answer(
        schedule_mentor_text, 
        reply_markup=_inline_markup_select_mentors_fcs
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectMentorScheduleFSM.select_mentor_schedule)


@router.callback_query(SelectMentorScheduleFSM.select_mentor_schedule)
@event_handler(admin_check=False, clear_state=False)
async def schedule_mentor_check(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle mentor selection for schedule viewing.
    
    Processes mentor selection and sends mentor's schedule.
    
    Args:
        cb: Mentor selection callback query.
        state: FSM context for state management.
    """
    if not cb.from_user or not cb.data:
        return

    user_id = cb.from_user.id
    mentor_name = _mentors_dict.get(cb.data)

    if not mentor_name:
        print(f"Invalid mentor key: {cb.data}")
        return

    state_data = await state.get_data()
    message_id = state_data.get("message_id")

    if not message_id or not cb.message:
        return

    chat_id = cb.message.chat.id

    try:
        # Update message with selected mentor
        await container.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=choosen_schedule_mentor_text.format(mentor=mentor_name),
            parse_mode="HTML",
            reply_markup=None,
        )

        # Send mentor's schedule
        await schedule_service.send_mentor_schedule(user_id, mentor_name, "_mentor_schedule")

        # Update message with confirmation
        await container.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"👩‍🏫 Выбран преподаватель: <b>{mentor_name}</b>",
            parse_mode="HTML",
            reply_markup=None,
        )

    except Exception as e:
        print(f"Failed to process mentor schedule: {e}")

    await state.clear()

@router.message(Command("group_schedule"), F.chat.type == ChatType.PRIVATE)
@router.message(F.text == "👥 Расписание группы", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def schedule_group_handler(ms: Message, state: FSMContext) -> None:
    """Handle group schedule initiation.
    
    Shows group selection interface for schedule viewing.
    
    Args:
        ms: Group schedule command message.
        state: FSM context for state management.
    """
    if not ms.from_user:
        return

    message = await ms.answer(
        schedule_group_text, 
        reply_markup=_inline_markup_select_group
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectGroupScheduleFSM.select_group_schedule)


@router.callback_query(SelectGroupScheduleFSM.select_group_schedule)
@event_handler(admin_check=False, clear_state=False)
async def schedule_group_check(cb: CallbackQuery, state: FSMContext) -> None:
    """Handle group selection for schedule viewing.
    
    Processes group selection and sends group's schedule.
    
    Args:
        cb: Group selection callback query.
        state: FSM context for state management.
    """
    if not cb.from_user or not cb.data:
        return

    user_id = cb.from_user.id
    group = cb.data

    if not group:
        return

    state_data = await state.get_data()
    message_id = state_data.get("message_id")

    if not message_id or not cb.message:
        return

    chat_id = cb.message.chat.id

    try:
        # Update message with selected group
        await container.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=choosen_schedule_group_text.format(group=group),
            parse_mode="HTML",
            reply_markup=None,
        )

        # Send group's schedule
        await schedule_service.send_schedule_by_group(user_id, group, "_group_schedule")

        # Update message with confirmation
        await container.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"👥 Выбрана группа: <b>{group}</b>",
            parse_mode="HTML",
            reply_markup=None,
        )

    except Exception as e:
        print(f"Failed to process group schedule: {e}")

    await state.clear()
