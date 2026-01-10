import asyncio
import copy
import re

from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.media_group import MediaGroupBuilder
from config.paths import PATH_CALL_IMG
from config.themes import paths_to_photo_theme, themes_parameters

from .keyboard import build_inline_keyboard
from .utils import format_names


def sort_key(group):
    match = re.match(r"([A-ZА-Я]+)(\d+)", group)
    if match:
        letters = match.group(1)
        numbers = match.group(2)
        return (letters, int(numbers))
    return (group, 0)


async def get_groups_schedule_wrapper() -> list[str]:
    from services.schedule_service import ScheduleService

    return await ScheduleService().get_groups_schedule()


async def get_mentors_names_schedule_wrapper() -> dict[str, str]:
    from services.schedule_service import ScheduleService

    mentors_names = await ScheduleService().get_names_mentors()
    mentors_initials = format_names(mentors_names)

    mentors_dict = dict(zip(mentors_initials, mentors_names))

    return mentors_dict


mentors_dict = asyncio.run(get_mentors_names_schedule_wrapper())


async def create_groups_keyboard():
    groups = await get_groups_schedule_wrapper()
    groups = sorted(set(groups), key=sort_key)
    return InlineKeyboardMarkup(inline_keyboard=build_inline_keyboard(groups))  # type: ignore


async def create_mentors_names_keyboard():
    mentors_dict = await get_mentors_names_schedule_wrapper()
    mentors_names = [v for _, v in mentors_dict.items()]

    mentors_names = sorted(set(mentors_names), key=sort_key)
    return InlineKeyboardMarkup(inline_keyboard=build_inline_keyboard(mentors_names))  # type: ignore


async def create_mentors_fcs_keyboard():
    mentors_dict = await get_mentors_names_schedule_wrapper()
    mentors_fcs = [k for k, _ in mentors_dict.items()]

    mentors_fcs = sorted(set(mentors_fcs), key=sort_key)
    return InlineKeyboardMarkup(inline_keyboard=build_inline_keyboard(mentors_fcs))  # type: ignore


inline_status_list = [
    [
        InlineKeyboardButton(text="👩‍🏫 Преподаватель", callback_data="👩‍🏫 Преподаватель"),
        InlineKeyboardButton(text="👨‍🎓 Студент", callback_data="👨‍🎓 Студент"),
    ]
]

inliine_markup_select_status = InlineKeyboardMarkup(inline_keyboard=inline_status_list)
inline_markup_select_group = asyncio.run(create_groups_keyboard())
inline_markup_select_mentors_names = asyncio.run(create_mentors_names_keyboard())
inline_markup_select_mentors_fcs = asyncio.run(create_mentors_fcs_keyboard())


inline_markup_select_theme = InlineKeyboardMarkup(
    inline_keyboard=build_inline_keyboard(list(themes_parameters.keys()))  # type: ignore
)


inline_additional_functions_list = [
    [InlineKeyboardButton(text="🌐 Сайт колледжа", url="https://mtec.by/ru/")],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="📆 Расписание")],
    [
        InlineKeyboardButton(text="👨‍🎓 Учащиеся", url="https://mtec.by/ru/students/schedule"),
        InlineKeyboardButton(text="🧑‍🏫 Преподаватели", url="https://mtec.by/ru/workers/schedule"),
    ],
]

inline_additional_functions_list_extended = [
    [InlineKeyboardButton(text="🌐 Сайт колледжа", url="https://mtec.by/ru/")],
    [InlineKeyboardButton(text="📆 Расписание", callback_data="📆 Расписание")],
    [
        InlineKeyboardButton(text="👨‍🎓 Учащиеся", url="https://mtec.by/ru/students/schedule"),
        InlineKeyboardButton(text="🧑‍🏫 Преподаватели", url="https://mtec.by/ru/workers/schedule"),
    ],
    [InlineKeyboardButton(text="📑 Справки", url="http://178.124.196.1:84/anketa/Home/Spravka")],
]

inline_additional_functions_bot = [
    [InlineKeyboardButton(text="⚙️ Настройки", callback_data="⚙️ Настройки")],
    [InlineKeyboardButton(text="⚖️ Правовая информация", callback_data="⚖️ Правовая информация")],
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

inline_markup_additional_functions = InlineKeyboardMarkup(inline_keyboard=inline_additional_functions_list)
inline_markup_additional_functions_extended = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_list_extended
)
inline_markup_additional_functions_bot = InlineKeyboardMarkup(inline_keyboard=inline_additional_functions_bot)
inline_markup_additional_functions_social_networks = InlineKeyboardMarkup(
    inline_keyboard=inline_additional_functions_social_networks_list
)


reply_additional_functions_list = [
    [
        KeyboardButton(text="🕒 Расписание звонков"),
        KeyboardButton(text="📚 Моё расписание"),
    ],
    [
        KeyboardButton(text="👩‍🏫 Расписание преподавателя"),
        KeyboardButton(text="👥 Расписание группы"),
    ],
    [KeyboardButton(text="📖 Электронный журнал")],
    [KeyboardButton(text="🔍 Дополнительно"), KeyboardButton(text="💬 Помощь")],
]

reply_markup_additional_functions = ReplyKeyboardMarkup(keyboard=reply_additional_functions_list)


reply_additional_functions_list_admin = copy.deepcopy(reply_additional_functions_list)
reply_additional_functions_list_admin.append([KeyboardButton(text="⚙️ Админ панель")])
reply_markup_additional_functions_admin = ReplyKeyboardMarkup(keyboard=reply_additional_functions_list_admin)


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
        InlineKeyboardButton(text="Сообщение 👤", callback_data="Сообщение 👤"),
    ],
    [
        InlineKeyboardButton(text="Сообщение 👥", callback_data="Сообщение 👥"),
        InlineKeyboardButton(text="Сообщение 🫂", callback_data="Сообщение 🫂"),
    ],
]
inline_markup_admin_panel_tools = InlineKeyboardMarkup(inline_keyboard=inline_admin_panel_tools_list)


media_photo_themes = MediaGroupBuilder()
[media_photo_themes.add(type="photo", media=FSInputFile(path=photo)) for photo in paths_to_photo_theme]  # type: ignore

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
