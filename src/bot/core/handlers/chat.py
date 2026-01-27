from functools import wraps

from aiogram import Dispatcher, F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from core.dependencies import container
from phrases import group_welcome_text
from services.schedule_service import ScheduleService
from utils.markup import inline_markup_select_group, inline_markup_select_mentors_fcs, mentors_dict

from bot.services.database import ChatRepository

from ..fsm.states import ChatSelectGroupFSM, ChatSelectMentorNameFSM

router = Router()
private_router = Router()


def register(dp: Dispatcher):
    dp.include_router(router)


def is_admin():
    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            try:
                chat_id = event.chat.id
            except:
                chat_id = event.message.chat.id

            if event.from_user.id != chat_id:  # type: ignore
                try:
                    member = await event.bot.get_chat_member(chat_id, event.from_user.id)  # type: ignore
                    if member.status not in ["administrator", "creator"]:
                        await event.reply("❌ Настраивать бота могут только администраторы группы")
                        return
                except Exception as e:
                    print(e)
                    await event.reply("⚠️ Не удалось проверить права. Убедитесь, что бот - администратор группы.")

            return await func(event, *args, **kwargs)

        return wrapper

    return decorator


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added_to_group(event: ChatMemberUpdated):
    """Бота добавили в группу - РАБОТАЮЩАЯ ВЕРСИЯ"""
    chat = event.chat

    if chat.type in ["group", "supergroup"]:
        try:
            await container.bot.send_message(chat_id=chat.id, text=group_welcome_text, parse_mode=ParseMode.HTML)

            async for session in container.db_manager.get_session():  # type: ignore
                await ChatRepository.create_or_update_chat(session, chat.id)

        except Exception as e:
            print(e)


@router.message(Command("setup_group"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
@is_admin()
async def cmd_setup(message: Message, state: FSMContext):
    """Настройка бота в группе"""
    await message.reply("👥 Выберите необходимую группу:", reply_markup=inline_markup_select_group)
    await state.set_state(ChatSelectGroupFSM.select_group)


@router.message(Command("setup_mentor"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
@is_admin()
async def cmd_setup_mentor(message: Message, state: FSMContext):
    """Настройка бота в группе для преподавателя"""
    await message.reply("👩‍🏫 Выберите необходимого преподавателя:", reply_markup=inline_markup_select_mentors_fcs)
    await state.set_state(ChatSelectMentorNameFSM.select_mentor_name)


@router.message(Command("reset"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
@is_admin()
async def cmd_reset(message: Message, state: FSMContext):
    """Настройка бота в группе для преподавателя"""
    chat_id = message.chat.id

    await message.reply("⚙️ Настройки сброшены! ")

    async for session in container.db_manager.get_session():  # type: ignore
        await ChatRepository.unsubscribe(session, chat_id)

    await state.clear()


@router.message(Command("schedule"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def cmd_schedule(message: Message, state: FSMContext):
    """Настройка бота в группе для преподавателя"""
    chat_id = message.chat.id

    async for session in container.db_manager.get_session():  # type: ignore
        chat_info = await ChatRepository.get_chat_subscription_info(session, chat_id)

    if len(chat_info) == 1:
        return

    chat_id = chat_info["chat_id"]
    sub_group = chat_info["subscribed_to_group"]
    sub_mentor = chat_info["subscribed_to_mentor"]

    if sub_group:
        await ScheduleService.send_schedule_by_group(chat_id, sub_group, "_chat_schedule")

    if sub_mentor:
        await ScheduleService.send_mentor_schedule(chat_id, sub_mentor, "_chat_schedule")

    await state.clear()


@router.message(Command("settings"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def cmd_settings(message: Message, state: FSMContext):
    """Настройка бота в группе для преподавателя"""
    chat_id = message.chat.id

    async for session in container.db_manager.get_session():  # type: ignore
        chat_info = await ChatRepository.get_chat_subscription_info(session, chat_id)

    sub_group = chat_info["subscribed_to_group"]
    sub_mentor = chat_info["subscribed_to_mentor"]

    await message.reply(
        f"<b>⚙️ Настройки бота:</b>\n\n👥 Выбрана группа: <b>{sub_group}</b>\n👩‍🏫 Выбран преподаватель: <b>{sub_mentor}</b>",
        parse_mode=ParseMode.HTML,
    )

    await state.clear()


@router.callback_query(StateFilter(ChatSelectGroupFSM.select_group))
@is_admin()
async def selected_group_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора группы"""
    chat_id = callback_query.message.chat.id  # type: ignore
    data = callback_query.data

    sub_group = data
    await callback_query.answer(f"✅ Выбрана группа: {sub_group}")
    await callback_query.message.edit_text(f"👥 Выбрана группа: <b>{sub_group}</b>", parse_mode=ParseMode.HTML)  # type: ignore

    async for session in container.db_manager.get_session():  # type: ignore
        await ChatRepository.subscribe_to_group(session, chat_id, sub_group)  # type: ignore

    await state.clear()


@router.callback_query(StateFilter(ChatSelectMentorNameFSM.select_mentor_name))
@is_admin()
async def selected_mentor_name_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора преподавателя"""
    chat_id = callback_query.message.chat.id  # type: ignore
    data = callback_query.data

    sub_mentor = mentors_dict[data]  # type: ignore
    await callback_query.answer(f"✅ Выбран преподаватель: {sub_mentor}")
    await callback_query.message.edit_text(f"👩‍🏫 Выбран преподаватель: <b>{sub_mentor}</b>", parse_mode=ParseMode.HTML)  # type: ignore

    async for session in container.db_manager.get_session():  # type: ignore
        await ChatRepository.subscribe_to_mentor(session, chat_id, sub_mentor)

    await state.clear()
