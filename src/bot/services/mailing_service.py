from typing import Union

from aiolimiter import AsyncLimiter
from config.bot_config import ADMIN
from core.dependencies import container


class MessageSender:
    """A class for sending messages to users"""

    PARSE_MODE = "HTML"
    SEND_DELAY = 0.1

    def __init__(self) -> None:
        self.limiter = AsyncLimiter(10, 3)

    @classmethod
    async def _send_single_message(
        cls, user_id: Union[str, int], message: str, report_to_admin: bool = False
    ) -> bool:
        """The method of sending a single message"""
        try:
            await container.bot.send_message(
                user_id, message, parse_mode=cls.PARSE_MODE
            )

            if report_to_admin:
                await container.bot.send_message(
                    ADMIN, f"{user_id} - Сообщение доставлено ✅"
                )

            print(f"{user_id} - Сообщение доставлено ✅")
            return True

        except Exception as e:
            if report_to_admin:
                await container.bot.send_message(
                    ADMIN, f"{user_id} - Ошибка доставки ❌\n{str(e)}"
                )
            print(f"{user_id} - Сообщение не доставлено ❌\n{e}")
            return False

    @classmethod
    async def send_message_to_user(cls, user_id: Union[str, int], message: str) -> None:
        """Sends a message to one user with a report to the admin"""
        await cls._send_single_message(user_id, message, report_to_admin=True)

    async def send_message_to_all_users(self, message: str) -> None:
        """A method for sending a message to all users"""
        users_id = await container.db_users.get_users()
        failed_users = []

        for user_id in users_id:
            async with self.limiter:
                success = await self._send_single_message(user_id, message)
                if not success:
                    failed_users.append(user_id)

        if failed_users:
            print(
                f"Сообщение не доставлено {len(failed_users)} пользователям\n{failed_users}"
            )

    async def send_message_to_group(self, group: str, message: str) -> None:
        """A method for sending a message to a group of users"""
        users_id = await container.db_users.get_users_by_group(group)
        failed_users = []

        for user_id in users_id:
            async with self.limiter:
                success = await self._send_single_message(user_id, message)
                if not success:
                    failed_users.append(user_id)

        if failed_users:
            print(
                f"Сообщение не доставлено {len(failed_users)} пользователям группы\n{failed_users}"
            )
