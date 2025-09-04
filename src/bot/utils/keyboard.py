from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config.settings import settings_dict_text


def build_inline_keyboard(list_items: list[str]) -> list[InlineKeyboardButton]:
    inline_keyboard_buttons = []
    btns = []
    for group in list_items:
        btns.append(InlineKeyboardButton(text=group, callback_data=group))

        if len(btns) % 3 == 0:
            inline_keyboard_buttons.append(btns)
            btns = []

    if btns:
        inline_keyboard_buttons.append(btns)

    return inline_keyboard_buttons


def build_settings_keyboard(user_settings: dict[str, bool]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=settings_dict_text.get(setting)[value], callback_data=setting  # type: ignore
            )
        ]
        for setting, value in user_settings.items()
    ]

    buttons.insert(
        0,
        [
            InlineKeyboardButton(
                text="🌌 Стиль расписания", callback_data="🌌 Стиль расписания"
            )
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
