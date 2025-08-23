import os

from aiogram import Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from config.bot_config import ADMIN
from config.paths import WORKSPACE, PATH_DBs
from core.dependencies import container
from phrases import *
from services.mailing_service import MessageSender
from utils.markup import (
    FSInputFile,
    inline_markup_admin_panel_tools,
    inline_markup_select_group,
)

from ..filters.custom_filters import (
    BlockUserFilter,
    GetDBHashesFilter,
    GetDBUsersFilter,
    GetLogsFilter,
    GetSupportJournalFilter,
    SendMessageGroupFilter,
    SendMessageUserFilter,
    SendMessageUsersFilter,
)
from ..fsm.states import (
    BlockUserFSM,
    SendMessageGroupFSM,
    SendMessageUserFSM,
    SendMessageUsersFSM,
)
from ..middlewares.antispam import AntiSpamMiddleware
from ..middlewares.blacklist import BlacklistMiddleware
from .common import cancel_action_handler
from .decorators import event_handler

router = Router()
router.message.middleware(BlacklistMiddleware())
router.message.middleware(AntiSpamMiddleware())

message_sender = MessageSender()


def register(dp: Dispatcher):
    dp.include_router(router)


@router.message(F.text == "⚙️ Админ панель")
@event_handler()
async def admin_panel_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer(admin_panel_text, reply_markup=inline_markup_admin_panel_tools)


@router.callback_query(GetDBUsersFilter())
@event_handler()
async def get_db_users_callback(cb: CallbackQuery, state: FSMContext) -> None:
    await container.bot.send_document(
        ADMIN, FSInputFile(path=f"{PATH_DBs}mtec_users.db")
    )


@router.callback_query(GetDBHashesFilter())
@event_handler()
async def get_db_hashes_callback(cb: CallbackQuery, state: FSMContext) -> None:
    await container.bot.send_document(
        ADMIN, FSInputFile(path=f"{PATH_DBs}schedule_hashes.db")
    )


@router.callback_query(GetLogsFilter())
@event_handler()
async def get_logs_callback(cb: CallbackQuery, state: FSMContext) -> None:
    await container.bot.send_document(ADMIN, FSInputFile(path=f"{WORKSPACE}logs.txt"))


@router.callback_query(GetSupportJournalFilter())
@event_handler()
async def get_support_callback(cb: CallbackQuery, state: FSMContext) -> None:
    await container.bot.send_document(
        ADMIN, FSInputFile(path=f"{WORKSPACE}support.txt")
    )


@router.callback_query(BlockUserFilter())
@event_handler()
async def block_user_callback(cb: CallbackQuery, state: FSMContext) -> None:
    await container.bot.send_message(ADMIN, block_user_text, parse_mode="HTML")
    await state.set_state(BlockUserFSM.block_user)


@router.message(BlockUserFSM.block_user)
@event_handler(log_event=False, clear_state=False)
async def block_user_enter_id(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    user_id = text

    with open(f"{WORKSPACE}blacklist.txt", "r") as file:
        blocked_users = file.read()

    list_blocked_users = blocked_users.split("\n")

    if user_id in list_blocked_users:
        await ms.answer(user_in_blacklist_text)
    else:
        with open(f"{WORKSPACE}blacklist.txt", "a") as file:
            file.write("\n")
            file.write(user_id)

        await ms.answer(user_added_in_blacklist_text)

    await state.clear()


@router.callback_query(SendMessageUserFilter())
@event_handler()
async def send_message_user(state: FSMContext) -> None:
    await container.bot.send_message(ADMIN, send_message_user_text, parse_mode="HTML")
    await state.set_state(SendMessageUserFSM.send_message_enter_id)


@router.message(SendMessageUserFSM.send_message_enter_id)
@event_handler(log_event=False, clear_state=False)
async def send_message_user_enter_id(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    user_id = text
    await state.update_data(user_id=user_id)

    await container.bot.send_message(ADMIN, enter_send_message_text, parse_mode="HTML")
    await state.set_state(SendMessageUserFSM.send_message_enter_message)


@router.message(SendMessageUserFSM.send_message_enter_message)
@event_handler(log_event=False, clear_state=False)
async def send_message_user_enter_message(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    message_to_user = text
    data = await state.get_data()
    user_id = data.get("user_id")

    if not isinstance(user_id, (int, str)):
        return None

    await message_sender.send_message_to_user(user_id, message_to_user)
    await state.clear()


@router.callback_query(SendMessageUsersFilter())
@event_handler()
async def send_message_users(state: FSMContext) -> None:
    await container.bot.send_message(
        ADMIN, send_message_all_users_text, parse_mode="HTML"
    )
    await state.set_state(SendMessageUsersFSM.send_message_enter_message)


@router.message(SendMessageUsersFSM.send_message_enter_message)
@event_handler(log_event=False, clear_state=False)
async def send_message_users_enter_message(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    message = text
    await message_sender.send_message_to_all_users(message)
    await state.clear()


@router.callback_query(SendMessageGroupFilter())
@event_handler()
async def send_message_group(state: FSMContext) -> None:
    await container.bot.send_message(
        ADMIN,
        send_message_group_text,
        reply_markup=inline_markup_select_group,
        parse_mode="HTML",
    )
    await state.set_state(SendMessageGroupFSM.send_message_select_group)


@router.callback_query(SendMessageGroupFSM.send_message_select_group)
@event_handler(log_event=False, clear_state=False)
async def send_message_group_select_group(cb: CallbackQuery, state: FSMContext) -> None:
    group = cb.data

    if not isinstance(group, str):
        return

    users_id = await container.db_users.get_users_by_group(group)

    if not users_id:
        await container.bot.send_message(
            ADMIN, f"❌ Нет пользователей с группы {group}"
        )
        return

    await state.update_data(group=group)

    await container.bot.send_message(ADMIN, enter_send_message_text, parse_mode="HTML")
    await state.set_state(SendMessageGroupFSM.send_message_enter_message)


@router.message(SendMessageGroupFSM.send_message_enter_message)
@event_handler(log_event=False, clear_state=False)
async def send_message_group_enter_message(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    message_to_group = text

    data = await state.get_data()
    group = data.get("group")

    if not isinstance(group, str):
        return None

    await message_sender.send_message_to_group(group, message_to_group)
    await state.clear()
