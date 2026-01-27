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

from bot.services.database import UserRepository

from ..fsm.states import EJournalFSM
from .common import cancel_action_handler
from .decorators import event_handler

router = Router()


def register(dp: Dispatcher):
    dp.include_router(router)


@router.message(F.text == "📖 Электронный журнал", F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def ejournal_handler(ms: Message, state: FSMContext) -> None:
    user_id = ms.from_user is not None and ms.from_user.id

    async for session in container.db_manager.get_session():  # type: ignore
        user_info: list = await UserRepository.get_user_ejournal_info(session, user_id)

    if not user_info == []:
        await send_ejournal_file(user_id)
    else:
        await container.bot.send_message(user_id, no_data_text, parse_mode="HTML")
        await container.bot.send_message(user_id, enter_fio_text)
        await state.set_state(EJournalFSM.enter_username)


@router.message(EJournalFSM.enter_username, F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False, clear_state=False)
async def ejournal_enter_name(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    username = text
    await state.update_data(username=username)

    await ms.answer(enter_password_text)
    await state.set_state(EJournalFSM.enter_password)


@router.message(EJournalFSM.enter_password, F.chat.type == ChatType.PRIVATE)
async def ejournal_enter_password(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    data = await state.get_data()
    username = data.get("username")
    password = text

    user_id = ms.from_user is not None and ms.from_user.id

    if not username or not password:
        await ms.answer(incorrectly_entered_data_text, parse_mode="HTML")
        await ms.answer(
            "Введите данные...\n\n<i># Отменить действие можно командой\n/exit</i>",
            parse_mode="HTML",
        )
        await state.set_state(EJournalFSM.enter_username)
        return

    async for session in container.db_manager.get_session():  # type: ignore
        await UserRepository.update_ejournal_info(session, user_id, username, password)

    await ms.answer(correctly_entered_data_text, parse_mode="HTML")
    await send_ejournal_file(user_id)

    await state.clear()


@router.message(Command("change_ejournal_info"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def change_ejournal_info_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer(change_data_text, parse_mode="HTML")
    await ms.answer(enter_fio_text)
    await state.set_state(EJournalFSM.enter_username)


@router.message(Command("delete_ejournal_info"), F.chat.type == ChatType.PRIVATE)
@event_handler(admin_check=False)
async def delete_ejournal_info_handler(ms: Message, state: FSMContext) -> None:
    user_id = ms.from_user is not None and ms.from_user.id

    async for session in container.db_manager.get_session():  # type: ignore
        await UserRepository.delete_ejournal_info(session, user_id)

    await ms.answer(deleted_user_ejournal_info_text)
