from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from core.dependencies import container
from phrases import *
from services.journal_service import send_ejournal_file

from ..fsm.states import EJournalFSM
from ..middlewares.antispam import AntiSpamMiddleware
from ..middlewares.blacklist import BlacklistMiddleware
from .common import cancel_action_handler
from .decorators import event_handler

router = Router()
router.message.middleware(BlacklistMiddleware())
router.message.middleware(AntiSpamMiddleware())


def register(dp: Dispatcher):
    dp.include_router(router)


@router.message(F.text == "📙 Электронный журнал")
@event_handler(admin_check=False)
async def ejournal_handler(ms: Message, state: FSMContext) -> None:
    user_id = ms.from_user is not None and ms.from_user.id
    user_info: list = await container.db_users.get_user_ejournal_info(user_id)

    if not user_info == []:
        await send_ejournal_file(user_id)
    else:
        await container.bot.send_message(user_id, no_data_text, parse_mode="HTML")
        await container.bot.send_message(user_id, enter_fio_text)
        await state.set_state(EJournalFSM.enter_username)


@router.message(EJournalFSM.enter_username)
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


@router.message(EJournalFSM.enter_password)
async def ejournal_enter_password(ms: Message, state: FSMContext) -> None:
    text = str(ms.text).strip()

    if text == "/exit":
        await cancel_action_handler(ms, state)
        return

    data = await state.get_data()
    username = data.get("username")
    password = text

    user_id = ms.from_user is not None and ms.from_user.id
    user_info: list = [username, password]

    if not username or not password:
        await ms.answer(incorrectly_entered_data_text, parse_mode="HTML")
        await ms.answer(
            "Введите данные...\n\n<i># Отменить действие можно командой\n/exit</i>",
            parse_mode="HTML",
        )
        await state.set_state(EJournalFSM.enter_username)
        return

    await container.db_users.add_user_ejournal_info(user_id, user_info)

    await ms.answer(correctly_entered_data_text, parse_mode="HTML")
    await send_ejournal_file(user_id)

    await state.clear()


@router.message(Command("change_ejournal_info"))
@event_handler(admin_check=False)
async def change_ejournal_info_handler(ms: Message, state: FSMContext) -> None:
    await ms.answer(change_data_text, parse_mode="HTML")
    await ms.answer(enter_fio_text)
    await state.set_state(EJournalFSM.enter_username)


@router.message(Command("delete_ejournal_info"))
@event_handler(admin_check=False)
async def delete_ejournal_info_handler(ms: Message, state: FSMContext) -> None:
    user_id = ms.from_user is not None and ms.from_user.id

    await container.db_users.delete_user_ejournal_info(user_id)
    await ms.answer(deleted_user_ejournal_info_text)
