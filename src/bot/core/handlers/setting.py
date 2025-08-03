from aiogram import Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from config.settings import settings_dict_text
from config.themes import themes_names
from core.dependencies import container
from phrases import *
from utils.keyboard import build_settings_keyboard
from utils.markup import inline_markup_select_theme, media_photo_themes

from ..filters.custom_filters import ScheduleStyle
from ..fsm.states import ChangeSettingsFSM, SelectThemeFSM
from ..middlewares.antispam import AntiSpamMiddleware
from ..middlewares.blacklist import BlacklistMiddleware
from .decorators import event_handler

router = Router()
router.message.middleware(BlacklistMiddleware())
router.message.middleware(AntiSpamMiddleware())


def register(dp: Dispatcher):
    dp.include_router(router)


@router.callback_query(ScheduleStyle())
@event_handler(admin_check=False)
async def select_theme_handler(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user is not None and cb.from_user.id
    user_theme = container.db_users.get_theme_by_user_id(user_id)

    media_group_message = await container.bot.send_media_group(
        user_id, media_photo_themes
    )

    need_to_delete = []
    amount_items = len(media_group_message)
    [
        need_to_delete.append(media_group_message[item].message_id)
        for item in range(0, amount_items)
    ]
    await state.update_data(need_to_delete=need_to_delete)

    await container.bot.send_message(
        user_id,
        change_theme_text.format(user_theme=user_theme),
        reply_markup=inline_markup_select_theme,
        parse_mode="HTML",
    )

    await state.set_state(SelectThemeFSM.select_theme)


@router.callback_query(SelectThemeFSM.select_theme)
@event_handler(admin_check=False, clear_state=False)
async def select_theme_callback(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    user_theme = cb.data

    if not user_theme in themes_names:
        return None

    container.db_users.change_user_theme(user_id, user_theme)

    data = await state.get_data()
    need_to_delete = data.get("need_to_delete")

    if not isinstance(need_to_delete, list):
        return None

    await container.bot.delete_messages(cb.from_user.id, need_to_delete)

    if isinstance(cb.message, Message):
        await cb.message.delete()

    await container.bot.send_message(
        user_id,
        selected_theme_text.format(user_theme=user_theme),
        parse_mode="HTML",
    )

    await state.clear()


@router.message(F.text == "⚙️ Настройки")
@event_handler(admin_check=False)
async def settings_handler(ms: Message, state: FSMContext) -> None:
    user_id = ms.from_user is not None and ms.from_user.id

    user_settings = container.db_users.get_user_settigs(user_id)
    keyboard = build_settings_keyboard(user_settings)

    await ms.answer(settings_text)
    sent_message = await ms.answer(
        settings_help_text, parse_mode="HTML", reply_markup=keyboard
    )

    await state.update_data(message_id=sent_message.message_id)
    await state.set_state(ChangeSettingsFSM.change)


@router.callback_query(ChangeSettingsFSM.change)
@event_handler(admin_check=False, clear_state=False)
async def change_settings(cb: CallbackQuery, state: FSMContext) -> None:
    user_action = cb.data
    if user_action not in settings_dict_text:
        return

    user_id = cb.from_user.id
    user_settings = container.db_users.get_user_settigs(user_id)
    message_id = (await state.get_data()).get("message_id")

    # Переключаем настройку
    current_value = user_settings.get(user_action)
    container.db_users.change_user_settings(user_action, not current_value, user_id)

    # Обновляем настройки и клавиатуру
    user_settings = container.db_users.get_user_settigs(user_id)
    keyboard = build_settings_keyboard(user_settings)

    chat_id = cb.message.chat.id if cb.message is not None else -1

    await container.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=settings_help_text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
