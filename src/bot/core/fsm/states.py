from aiogram.fsm.state import State, StatesGroup


class SelectGroupFSM(StatesGroup):
    select_group = State()


class SelectGroupFriendFSM(StatesGroup):
    select_group_friend = State()


class SupportFSM(StatesGroup):
    support = State()


class SelectThemeFSM(StatesGroup):
    select_theme = State()


class EJournalFSM(StatesGroup):
    enter_username = State()
    enter_password = State()


class AdminPanelFSM(StatesGroup):
    select_action = State()


class BlockUserFSM(StatesGroup):
    block_user = State()


class SendMessageUserFSM(StatesGroup):
    send_message_enter_id = State()
    send_message_enter_message = State()


class SendMessageUsersFSM(StatesGroup):
    send_message_enter_message = State()


class SendMessageGroupFSM(StatesGroup):
    send_message_select_group = State()
    send_message_enter_message = State()


class ChangeSettingsFSM(StatesGroup):
    change = State()
