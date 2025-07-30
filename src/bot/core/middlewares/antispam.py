import time
from collections import defaultdict

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, limit=5, interval=15):
        self.user_timestamps = defaultdict(list)
        self.limit = limit
        self.interval = interval

    async def __call__(self, handler, event: Message, data):
        user_id = event.from_user.id  # type: ignore
        current_time = time.time()

        self.user_timestamps[user_id] = [
            t for t in self.user_timestamps[user_id] if current_time - t < self.interval
        ]

        if len(self.user_timestamps[user_id]) >= self.limit:
            await event.answer("⚠️ Слишком много запросов! Пожалуйста, подождите.")
            return

        self.user_timestamps[user_id].append(current_time)
        return await handler(event, data)
