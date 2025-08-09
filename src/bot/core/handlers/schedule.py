from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from core.dependencies import container
from phrases import *
from services.schedule_service import ScheduleService
from utils.markup import inline_markup_select_group, media_call_schedule_photos

from ..fsm.states import SelectGroupFriendFSM
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
@event_handler(admin_check=False)
async def resend_schedule_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer(checking_schedule_text)

    user_id = ms.from_user is not None and ms.from_user.id
    user_group = container.db_users.get_group_by_user_id(user_id)

    await schedule_service.send_schedule_by_group(user_id, user_group, "_resend")


@router.message(F.text == "🕒 Расписание звонков")
@event_handler(admin_check=False)
async def send_call_schedule_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer_media_group(media_call_schedule_photos)


@router.message(F.text == "👤 Расписание друга")
@event_handler(admin_check=False)
async def schedule_friend(ms: Message, state: FSMContext) -> None:
    message = await ms.answer(
        friend_group_text, reply_markup=inline_markup_select_group
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectGroupFriendFSM.select_group_friend)


@router.callback_query(SelectGroupFriendFSM.select_group_friend)
@event_handler(admin_check=False, clear_state=False)
async def schedule_friend_check(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    friend_group = cb.data

    if friend_group is None:
        return

    state_data = await state.get_data()
    message_need_edit_id = state_data.get("message_id")

    chat_id = cb.message.chat.id if cb.message is not None else -1

    await container.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_need_edit_id,
        text=changed_friend_group_text.format(friend_group=friend_group),
        parse_mode="HTML",
        reply_markup=None,
    )

    await schedule_service.send_schedule_by_group(
        user_id, friend_group, "_friend_schedule"
    )

    await state.clear()
