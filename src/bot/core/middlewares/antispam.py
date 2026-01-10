import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(
        self,
        limit: int = 10,
        interval: int = 15,
        warn_threshold: int = 7,
        mute_duration: int = 120,
        check_repetition: bool = True,
        check_links: bool = True,
    ):
        self.user_timestamps = defaultdict(list)
        self.user_warnings = defaultdict(int)
        self.muted_users: Dict[int, float] = {}
        self.limit = limit
        self.interval = interval
        self.warn_threshold = warn_threshold
        self.mute_duration = mute_duration
        self.check_repetition = check_repetition
        self.check_links = check_links

        # Для проверки повторений
        self.last_messages = defaultdict(list)
        self.user_links = defaultdict(list)

    async def __call__(self, handler, event: Message, data: Dict[str, Any]):
        user_id = event.from_user.id  # type: ignore
        current_time = time.time()

        if await self._check_mute(user_id, current_time):
            await event.answer("⛔ Вы временно ограничены в отправке сообщений.")
            return

        self._clean_old_data(user_id, current_time)

        if await self._check_flood(user_id, current_time):
            await self._handle_flood(event, user_id, current_time)
            return

        if self.check_repetition and await self._check_repetition(event, user_id, current_time):
            await self._handle_spam(event, user_id, "Повторение сообщений")
            return

        if self.check_links and event.text and await self._check_links(event, user_id, current_time):
            await self._handle_spam(event, user_id, "Флуд ссылками")
            return

        self.user_timestamps[user_id].append(current_time)

        return await handler(event, data)

    async def _check_mute(self, user_id: int, current_time: float) -> bool:
        if user_id in self.muted_users:
            mute_end = self.muted_users[user_id]
            if current_time < mute_end:
                return True
            else:
                del self.muted_users[user_id]
        return False

    def _clean_old_data(self, user_id: int, current_time: float):
        self.user_timestamps[user_id] = [t for t in self.user_timestamps[user_id] if current_time - t < self.interval]

        if user_id in self.last_messages:
            self.last_messages[user_id] = [
                (msg, t)
                for msg, t in self.last_messages[user_id]
                if current_time - t < 10  # 10 секунд для проверки повторений
            ]

        if user_id in self.user_links:
            self.user_links[user_id] = [
                t for t in self.user_links[user_id] if current_time - t < 60  # 60 секунд для проверки ссылок
            ]

    async def _check_flood(self, user_id: int, current_time: float) -> bool:
        if len(self.user_timestamps[user_id]) >= self.limit:
            return True
        return False

    async def _check_repetition(self, event: Message, user_id: int, current_time: float) -> bool:
        if not event.text or len(event.text) < 3:
            return False

        self.last_messages[user_id].append((event.text, current_time))

        recent_messages = [msg for msg, t in self.last_messages[user_id]]
        if recent_messages.count(event.text) >= 7:
            return True

        return False

    async def _check_links(self, event: Message, user_id: int, current_time: float) -> bool:
        import re

        link_patterns = [r"https?://", r"www\.", r"t\.me/", r"@[A-Za-z0-9_]{5,}"]
        has_link = any(re.search(pattern, event.text) for pattern in link_patterns)  # type: ignore

        if has_link:
            self.user_links[user_id].append(current_time)

            if len(self.user_links[user_id]) > 2:
                return True

        return False

    async def _handle_flood(self, event: Message, user_id: int, current_time: float):
        self.user_warnings[user_id] += 1

        if self.user_warnings[user_id] >= self.warn_threshold:
            mute_until = current_time + self.mute_duration
            self.muted_users[user_id] = mute_until

            mute_time = datetime.fromtimestamp(mute_until).strftime("%H:%M:%S")

            await event.answer(
                f"⛔ Вы превысили лимит сообщений. Ограничение до {mute_time}\n"
                f"Предупреждение {self.user_warnings[user_id]}/{self.warn_threshold}"
            )
            self.user_warnings[user_id] = 0
        else:
            warnings_left = self.warn_threshold - self.user_warnings[user_id]
            await event.answer(
                f"⚠️ Слишком много запросов! Подождите.\n"
                f"Предупреждение {self.user_warnings[user_id]}/{self.warn_threshold}\n"
                f"До ограничения осталось: {warnings_left}"
            )

    async def _handle_spam(self, event: Message, user_id: int, reason: str):
        print(f"[SPAM DETECTED] User: {user_id}, Reason: {reason}, Time: {datetime.now()}")

        current_time = time.time()
        mute_until = current_time + self.mute_duration * 2  # Удвоенное время за спам
        self.muted_users[user_id] = mute_until
        mute_time = datetime.fromtimestamp(mute_until).strftime("%H:%M:%S")

        await event.answer(f"⛔ Обнаружено подозрительное поведение ({reason}).\n" f"Вы ограничены до {mute_time}")

    async def reset_user(self, user_id: int):
        self.user_timestamps.pop(user_id, None)
        self.user_warnings.pop(user_id, None)
        self.muted_users.pop(user_id, None)
        self.last_messages.pop(user_id, None)
        self.user_links.pop(user_id, None)

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        current_time = time.time()
        messages_count = len(self.user_timestamps.get(user_id, []))

        return {
            "messages_in_interval": messages_count,
            "messages_limit": self.limit,
            "warnings": self.user_warnings.get(user_id, 0),
            "warn_threshold": self.warn_threshold,
            "is_muted": user_id in self.muted_users and current_time < self.muted_users[user_id],
            "mute_until": self.muted_users.get(user_id),
        }
