from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message
from config.paths import WORKSPACE


class BlacklistMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()

    async def __call__(self, handler, event: Message, data):
        with open(f"{WORKSPACE}blacklist.txt", "r") as file:
            blacklist: list = file.read().split("\n")

        user_id = event.from_user.id if event.from_user is not None else 0

        if str(user_id) in blacklist:
            print(f"Пользователь {user_id} заблокирован!")
            return

        return await handler(event, data)
