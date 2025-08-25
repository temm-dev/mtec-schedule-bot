from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from config.bot_config import ADMIN
from config.paths import WORKSPACE
from core.dependencies import container
from phrases import *
from services.schedule_service import ScheduleService
from utils.markup import (
    inline_markup_additional_functions,
    inline_markup_additional_functions_bot,
    inline_markup_additional_functions_extended,
    inline_markup_additional_functions_social_networks,
    inline_markup_select_group,
    reply_markup_additional_functions,
    reply_markup_additional_functions_admin,
)

from ..filters.custom_filters import LegalInformationFilter
from ..fsm.states import SelectGroupFSM, SupportFSM
from ..middlewares.antispam import AntiSpamMiddleware
from ..middlewares.blacklist import BlacklistMiddleware
from .decorators import event_handler

router = Router()
router.message.middleware(BlacklistMiddleware())
router.message.middleware(AntiSpamMiddleware())

schedule_service = ScheduleService()


def register(dp: Dispatcher):
    dp.include_router(router)


@router.callback_query(LegalInformationFilter())
@event_handler(admin_check=False, clear_state=True)
async def legal_information_callback(cb: CallbackQuery, state: FSMContext) -> None:
    await container.bot.send_message(
        cb.from_user.id, legal_information, parse_mode="HTML"
    )


@router.message(F.content_type.in_({"photo", "video", "audio", "document", "sticker"}))
@event_handler(admin_check=False, clear_state=True)
async def non_text_message_handler(ms: Message):
    await ms.answer(non_text_message_text)


@router.message(Command("exit"))
@event_handler(admin_check=False)
async def cancel_action_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer(exit_text)


@router.message(Command("restart"))
@event_handler(log_event=False, admin_check=False)
async def restart_bot_handler(ms: Message, state: FSMContext) -> None:
    user_id = ms.from_user is not None and ms.from_user.id
    print(f"{user_id} - Bot restarted")

    markup = reply_markup_additional_functions
    if user_id == ADMIN:
        markup = reply_markup_additional_functions_admin

    await ms.answer(restart_text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("start"))
@event_handler(admin_check=False)
async def start_handler(ms: Message, state: FSMContext) -> None:
    message1 = await ms.answer(text=welcome_text)

    message2 = await ms.answer(
        text=select_group_text, reply_markup=inline_markup_select_group
    )

    await state.update_data(messages_id=[message1.message_id, message2.message_id])
    await state.set_state(SelectGroupFSM.select_group)


@router.callback_query(SelectGroupFSM.select_group)
@event_handler(admin_check=False, clear_state=False)
async def selected_group_callback(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    user_group = cb.data

    if not isinstance(user_group, str):
        return None

    user_in: bool = await container.db_users.check_user_in_db(user_id)

    if not user_in:
        await container.db_users.add_user_into_db(user_id, user_group)
    else:
        await container.db_users.change_user_group(user_id, user_group)

    state_data = await state.get_data()
    messages_need_delete_id = state_data.get("messages_id")
    chat_id = cb.message.chat.id if cb.message is not None else -1

    if messages_need_delete_id:
        await container.bot.delete_messages(
            chat_id=chat_id, message_ids=messages_need_delete_id
        )

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


@router.message(Command("change_group"))
@event_handler(admin_check=False)
async def change_group_handler(ms: Message, state: FSMContext) -> None:
    message = await ms.answer(
        change_group_text, reply_markup=inline_markup_select_group
    )
    await state.update_data(message_id=message.message_id)
    await state.set_state(SelectGroupFSM.select_group)


@router.message(F.text == "🔍 Дополнительно")
@event_handler(admin_check=False)
async def additionally_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer(
        base_additionally_text,
        reply_markup=inline_markup_additional_functions_extended,
    )
    await ms.answer(
        sn_additionally_text,
        reply_markup=inline_markup_additional_functions_social_networks,
    )
    await ms.answer(
        bot_additionally_text, reply_markup=inline_markup_additional_functions_bot
    )


@router.message(Command("support"))
@router.message(F.text == "❓ Помощь")
@event_handler(admin_check=False)
async def technical_support_handler(ms: Message, state: FSMContext) -> None:
    message1 = await ms.answer(support_text, parse_mode="HTML")
    message2 = await ms.answer(enter_message_text)

    await state.update_data(need_to_delete=[message1.message_id, message2.message_id])
    await state.set_state(SupportFSM.support)


@router.message(SupportFSM.support)
@event_handler(admin_check=False, clear_state=False)
async def technical_support_next_handler(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    data = await state.get_data()
    need_to_delete = data.get("need_to_delete")

    if not isinstance(need_to_delete, list):
        return None

    if ms.from_user is None:
        return

    user_id = ms.from_user.id
    user_username = ms.from_user.username
    user_firstname = ms.from_user.first_name
    user_lastname = ms.from_user.last_name

    await container.bot.delete_messages(user_id, need_to_delete)
    await state.update_data(must_be_deleted=[])

    await ms.answer(thx_for_message_text)

    with open(f"{WORKSPACE}support.txt", "a", encoding="utf-8") as file:
        file.write(
            f"📋 Новое сообщение в тех. поддержку от @{user_username} - "
            f"{user_firstname} - {user_lastname} - {user_id}:\n"
            f"{ms.text}\n\n"
        )

    await state.clear()
