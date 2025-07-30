import asyncio
from typing import Union

from config.bot_config import ADMIN
from core.dependencies import container


class MessageSender:
    """Класс для рассылки сообщений пользователям"""
    
    PARSE_MODE = "HTML"
    SEND_DELAY = 0.1

    @classmethod
    async def _send_single_message(
        cls,
        user_id: Union[str, int],
        message: str,
        report_to_admin: bool = False
    ) -> bool:
        """Метод отправки одного сообщения"""
        try:
            await container.bot.send_message(user_id, message, parse_mode=cls.PARSE_MODE)
            
            if report_to_admin:
                await container.bot.send_message(
                    ADMIN, 
                    f"{user_id} - Сообщение доставлено ✅"
                )
            return True
            
        except Exception as e:
            if report_to_admin:
                await container.bot.send_message(
                    ADMIN, 
                    f"{user_id} - Ошибка доставки ❌\n{str(e)}"
                )
            return False

    @classmethod
    async def send_message_to_user(
        cls,
        user_id: Union[str, int],
        message: str
    ) -> None:
        """Отправляет сообщение одному пользователю с отчетом админу"""
        await cls._send_single_message(user_id, message, report_to_admin=True)

    @classmethod
    async def send_message_to_all_users(
        cls,
        message: str
    ) -> None:
        """Отправляет сообщение всем пользователям"""
        users_id = container.db_users.get_users()
        failed_users = []

        for user_id in users_id:
            success = await cls._send_single_message(user_id, message)
            if not success:
                failed_users.append(user_id)
            await asyncio.sleep(cls.SEND_DELAY)

        if failed_users:
            print(f"Сообщение не доставлено {len(failed_users)} пользователям\n{failed_users}")

    @classmethod
    async def send_message_to_group(
        cls,
        group: str,
        message: str
    ) -> None:
        """Отправляет сообщение группе пользователей"""
        users_id = container.db_users.get_users_by_group(group)
        failed_users = []

        for user_id in users_id:
            success = await cls._send_single_message(user_id, message)
            if not success:
                failed_users.append(user_id)
            await asyncio.sleep(cls.SEND_DELAY)

        if failed_users:
            print(f"Сообщение не доставлено {len(failed_users)} пользователям группы")