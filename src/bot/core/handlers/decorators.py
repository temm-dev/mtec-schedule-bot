from functools import wraps
from typing import Union

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from config.bot_config import ADMIN
from utils.formatters import format_error_message
from utils.log import log


def event_handler(
    log_event: bool = True, clear_state: bool = True, admin_check: bool = True
):
    def decorator(func):
        @wraps(func)
        async def wrapper(
            event: Union[Message, CallbackQuery], state: FSMContext, *args, **kwargs
        ):
            try:
                if log_event:
                    if isinstance(event, Message):
                        await log(event)
                    elif isinstance(event, CallbackQuery):
                        await log(event.message)

                if (
                    admin_check
                    and event.from_user is not None
                    and event.from_user.id != ADMIN
                ):
                    if isinstance(event, CallbackQuery):
                        await event.answer("⛔ Доступ запрещен!", show_alert=True)
                    return None

                if clear_state:
                    current_state = await state.get_state()
                    if current_state:
                        await state.clear()

                return await func(event, state, *args, **kwargs)

            except Exception as e:
                print(format_error_message(func.__name__, e))

        return wrapper

    return decorator
