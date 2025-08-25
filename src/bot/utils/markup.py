import asyncio
import copy

from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.media_group import MediaGroupBuilder
from config.paths import PATH_CALL_IMG
from config.themes import paths_to_photo_theme, themes_parameters

from .keyboard import build_inline_keyboard


async def get_groups_schedule_wrapper() -> list[str]:
    from services.schedule_service import ScheduleService

    return await ScheduleService().get_groups_schedule()


async def create_groups_keyboard():
    groups = await get_groups_schedule_wrapper()
    return InlineKeyboardMarkup(inline_keyboard=build_inline_keyboard(groups))  # type: ignore


inline_markup_select_group = asyncio.run(create_groups_keyboard())
inline_markup_select_theme = InlineKeyboardMarkup(
    inline_keyboard=build_inline_keyboard(list(themes_parameters.keys()))  # type: ignore
)


inline_additional_functions_list = [
    [InlineKeyboardButton(text="🌐 Сайт колледжа", url="https://mtec.by/ru/")],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="📆 Расписание")],
    [
        InlineKeyboardButton(
            text="👨‍🎓 Учащиеся", url="https://mtec.by/ru/students/schedule"
        ),
        InlineKeyboardButton(
            text="🧑‍🏫 Преподаватели", url="https://mtec.by/ru/workers/schedule"
        ),
    ],
]

inline_additional_functions_list_extended = [
    [InlineKeyboardButton(text="🌐 Сайт колледжа", url="https://mtec.by/ru/")],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="📆 Расписание")],
    [
        InlineKeyboardButton(
            text="👨‍🎓 Учащиеся", url="https://mtec.by/ru/students/schedule"
        ),
        InlineKeyboardButton(
            text="🧑‍🏫 Преподаватели", url="https://mtec.by/ru/workers/schedule"
        ),
    ],
    [
        InlineKeyboardButton(
            text="📑 Справки", url="http://178.124.196.1:84/anketa/Home/Spravka"
        )
    ],
]

inline_additional_functions_bot = [
    [
        InlineKeyboardButton(
            text="❗ Правовая информация", callback_data="❗ Правовая информация"
        )
    ]
]

inline_additional_functions_social_networks_list = [
    [
        InlineKeyboardButton(text="Instagram", url="https://www.instagram.com/mtecby/"),
        InlineKeyboardButton(text="TikTok", url="https://www.tiktok.com/@mtec_molo"),
    ],
    [
        InlineKeyboardButton(
            text="YouTube",
            url="https://www.youtube.com/channel/UC4B6JgjjmeZrhMnGlAx9bew",
        ),
        InlineKeyboardButton(text="Facebook", url="https://www.facebook.com/mtecbks/"),
    ],
    [InlineKeyboardButton(text="Vk", url="https://vk.com/mtecby")],
]

inline_markup_additional_functions = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_list
)
inline_markup_additional_functions_extended = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_list_extended
)
inline_markup_additional_functions_bot = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_bot
)
inline_markup_additional_functions_social_networks = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_social_networks_list
)


reply_additional_functions_list = [
    [KeyboardButton(text="🕒 Расписание звонков")],
    [KeyboardButton(text="📙 Электронный журнал")],
    [KeyboardButton(text="👤 Расписание друга")],
    [KeyboardButton(text="🔍 Дополнительно"), KeyboardButton(text="⚙️ Настройки")],
    [KeyboardButton(text="❓ Помощь")],
]

reply_markup_additional_functions = ReplyKeyboardMarkup(
    keyboard=reply_additional_functions_list
)


reply_additional_functions_list_admin = copy.deepcopy(reply_additional_functions_list)
reply_additional_functions_list_admin.append([KeyboardButton(text="⚙️ Админ панель")])
reply_markup_additional_functions_admin = ReplyKeyboardMarkup(
    keyboard=reply_additional_functions_list_admin
)


inline_admin_panel_tools_list = [
    [InlineKeyboardButton(text="🗂️ DATABASE 🗂️", callback_data="🗂️ DATABASE 🗂️")],
    [
        InlineKeyboardButton(text="users 📄", callback_data="users 📄"),
        InlineKeyboardButton(text="hashes 📄", callback_data="hashes 📄"),
    ],
    [
        InlineKeyboardButton(text="logs 📄", callback_data="logs 📄"),
        InlineKeyboardButton(text="support 📄", callback_data="support 📄"),
    ],
    [InlineKeyboardButton(text="⼈ USERS ⼈", callback_data="⼈ USERS ⼈")],
    [
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data="🚫 Заблокировать"),
        InlineKeyboardButton(
            text="Сообщение 👤", callback_data="Сообщение 👤"
        ),
    ],
    [
        InlineKeyboardButton(
            text="Сообщение 👥", callback_data="Сообщение 👥"
        ),
        InlineKeyboardButton(
            text="Сообщение 🫂", callback_data="Сообщение 🫂"
        ),
    ],
]
inline_markup_admin_panel_tools = InlineKeyboardMarkup(
    inline_keyboard=inline_admin_panel_tools_list
)


media_photo_themes = MediaGroupBuilder()
[
    media_photo_themes.add(type="photo", media=FSInputFile(path=photo))  # type: ignore
    for photo in paths_to_photo_theme
]

media_photo_themes = media_photo_themes.build()


media_call_schedule_photos = MediaGroupBuilder()
media_call_schedule_photos.add(
    type="photo",  # type: ignore
    media=FSInputFile(path=f"{PATH_CALL_IMG}call_schedule_photo1.png"),
)  # type: ignore

media_call_schedule_photos.add(
    type="photo",  # type: ignore
    media=FSInputFile(path=f"{PATH_CALL_IMG}call_schedule_photo2.png"),
)  # type: ignore

media_call_schedule_photos = media_call_schedule_photos.build()
