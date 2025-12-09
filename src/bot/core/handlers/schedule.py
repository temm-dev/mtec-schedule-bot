from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from core.dependencies import container
from phrases import *
from services.schedule_service import ScheduleService
from utils.markup import (
    inline_markup_select_group,
    inline_markup_select_mentors_fcs,
    media_call_schedule_photos,
    mentors_dict,
)

from ..fsm.states import SelectGroupScheduleFSM, SelectMentorScheduleFSM
from ..middlewares.antispam import AntiSpamMiddleware
from ..middlewares.blacklist import BlacklistMiddleware
from .decorators import event_handler

router = Router()
router.message.middleware(BlacklistMiddleware())
router.message.middleware(AntiSpamMiddleware())

schedule_service = ScheduleService()


def register(dp: Dispatcher):
    dp.include_router(router)


@router.message(Command("resend_schedule"))
@router.message(F.text == "📚 Моё расписание")
@event_handler(admin_check=False)
async def resend_schedule_handler(ms: Message, state: FSMContext) -> None:
    message = await ms.answer(checking_schedule_text)

    user_id = ms.from_user is not None and ms.from_user.id

    user_status = await container.db_users.get_user_status(user_id)

    if user_status == "mentor":
        mentor_name = await container.db_users.get_mentor_name_by_id(user_id)

        if mentor_name is None:
            return

        await schedule_service.send_mentor_schedule(user_id, mentor_name, "_resend")
        await container.bot.delete_message(user_id, message.message_id)

    elif user_status == "student":
        user_group = await container.db_users.get_user_group(user_id)
        await schedule_service.send_schedule_by_group(user_id, user_group, "_resend")
        await container.bot.delete_message(user_id, message.message_id)


@router.message(F.text == "🔔 Расписание звонков")
@router.message(F.text == "🕒 Расписание звонков")
@event_handler(admin_check=False)
async def send_call_schedule_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer_media_group(media_call_schedule_photos)


@router.message(F.text == "👩‍🏫 Расписание преподавателя")
@event_handler(admin_check=False)
async def schedule_mentor(ms: Message, state: FSMContext) -> None:
    message = await ms.answer(
        schedule_mentor_text, reply_markup=inline_markup_select_mentors_fcs
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectMentorScheduleFSM.select_mentor_schedule)


@router.callback_query(SelectMentorScheduleFSM.select_mentor_schedule)
@event_handler(admin_check=False, clear_state=False)
async def schedule_mentor_check(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    mentor_name = mentors_dict[cb.data]  # type: ignore

    if mentor_name is None:
        return

    state_data = await state.get_data()
    message_need_edit_id = state_data.get("message_id")

    chat_id = cb.message.chat.id if cb.message is not None else -1

    await container.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_need_edit_id,
        text=choosen_schedule_mentor_text.format(mentor=mentor_name),
        parse_mode="HTML",
        reply_markup=None,
    )

    await schedule_service.send_mentor_schedule(
        user_id, mentor_name, "_mentor_schedule"
    )

    await container.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_need_edit_id,
        text="👩‍🏫 Выбран преподаватель: <b>{mentor}</b>".format(mentor=mentor_name),
        parse_mode="HTML",
        reply_markup=None,
    )

    await state.clear()


@router.message(F.text == "👥 Расписание группы")
@event_handler(admin_check=False)
async def schedule_group(ms: Message, state: FSMContext) -> None:
    message = await ms.answer(
        schedule_group_text, reply_markup=inline_markup_select_group
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectGroupScheduleFSM.select_group_schedule)


@router.callback_query(SelectGroupScheduleFSM.select_group_schedule)
@event_handler(admin_check=False, clear_state=False)
async def schedule_group_check(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    group = cb.data

    if group is None:
        return

    state_data = await state.get_data()
    message_need_edit_id = state_data.get("message_id")

    chat_id = cb.message.chat.id if cb.message is not None else -1

    await container.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_need_edit_id,
        text=choosen_schedule_group_text.format(group=group),
        parse_mode="HTML",
        reply_markup=None,
    )

    await schedule_service.send_schedule_by_group(user_id, group, "_group_schedule")

    await container.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_need_edit_id,
        text="👥 Выбрана группа: <b>{group}</b>".format(group=group),
        parse_mode="HTML",
        reply_markup=None,
    )

    await state.clear()
