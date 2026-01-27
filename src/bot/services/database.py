import ast
import json
from datetime import date as date_type
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.bot_config import SECRET_KEY
from config.paths import PATH_DBs
from cryptography.fernet import Fernet
from sqlalchemy import and_, delete, func, or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from .models import Base, Chat, ScheduleArchiveMentor, ScheduleArchiveStudent, ScheduleHash, User

cipher = Fernet(SECRET_KEY)


class DatabaseManager:
    """Основной класс для работы с базой данных через SQLAlchemy"""

    def __init__(self, db_url: str = f"sqlite+aiosqlite:///{PATH_DBs}bot_database.db"):
        self.engine = create_async_engine(db_url, echo=False, future=True)
        self.async_session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def init_db(self):
        """Инициализация базы данных (создание таблиц)"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ База данных инициализирована")

    async def get_session(self) -> AsyncSession:  # type: ignore
        """Получение сессии для работы с БД"""
        async with self.async_session() as session:
            try:
                yield session  # type: ignore
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


class UserRepository:
    """Репозиторий для работы с пользователями"""

    @staticmethod
    async def create_or_update_user(
        session: AsyncSession,
        user_id: int,
        user_status: str,
        mentor_name: Optional[str] = None,
        student_group: Optional[str] = None,
    ) -> User:
        """Создание или обновление пользователя"""
        try:
            # Проверяем существование пользователя
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if user:
                # Обновляем существующего пользователя
                user.user_status = user_status  # type: ignore
                user.mentor_name = mentor_name if mentor_name else None  # type: ignore
                user.student_group = student_group if student_group else None  # type: ignore
                print(f"👤 Пользователь обновлен 🔄 | {user_id}")
            else:
                # Создаем нового пользователя
                user = User(
                    user_id=user_id, user_status=user_status, mentor_name=mentor_name, student_group=student_group
                )
                session.add(user)
                print(f"👤 Пользователь добавлен 🆕 | {user_id} - {student_group or mentor_name}")

            await session.commit()
            return user

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при работе с пользователем: {e}")
            raise

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        result = await session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def user_exists(session: AsyncSession, user_id: int) -> bool:
        """Проверка существования пользователя"""
        result = await session.execute(select(func.count()).select_from(User).where(User.user_id == user_id))
        return result.scalar() > 0  # type: ignore

    @staticmethod
    async def get_user_status(session: AsyncSession, user_id: int) -> str:
        """Получение статуса пользователя"""
        result = await session.execute(select(User.user_status).where(User.user_id == user_id))
        status = result.scalar_one_or_none()
        return status or ""

    @staticmethod
    async def get_all_users(session: AsyncSession) -> List[int]:
        """Получение всех ID пользователей"""
        result = await session.execute(select(User.user_id))
        return [row[0] for row in result.all()]

    @staticmethod
    async def get_all_groups(session: AsyncSession) -> List[str]:
        """Получение всех групп студентов"""
        result = await session.execute(select(User.student_group).where(User.user_status == "student").distinct())
        groups = [row[0] for row in result.all() if row[0]]
        return list(set(groups))

    @staticmethod
    async def get_users_by_group(session: AsyncSession, group: str, toggle_schedule: bool = False) -> List[int]:
        """Получение пользователей по группе"""
        result = await session.execute(
            select(User.user_id).where(
                and_(
                    User.user_status == "student", User.student_group == group, User.toggle_schedule == toggle_schedule
                )
            )
        )
        return [row[0] for row in result.all()]

    @staticmethod
    async def get_users_by_group_and_theme(
        session: AsyncSession, group: str, theme: str = "Classic", toggle_schedule: bool = False
    ) -> List[int]:
        """Получение пользователей по группе и теме"""
        result = await session.execute(
            select(User.user_id).where(
                and_(User.student_group == group, User.user_theme == theme, User.toggle_schedule == toggle_schedule)
            )
        )
        return [row[0] for row in result.all()]

    @staticmethod
    async def get_user_group(session: AsyncSession, user_id: int) -> str:
        """Получение группы пользователя"""
        result = await session.execute(select(User.student_group).where(User.user_id == user_id))
        group = result.scalar_one_or_none()
        return group or ""

    @staticmethod
    async def get_user_theme(session: AsyncSession, user_id: int) -> str:
        """Получение темы пользователя"""
        result = await session.execute(select(User.user_theme).where(User.user_id == user_id))
        theme = result.scalar_one_or_none()
        return theme or "Classic"

    @staticmethod
    async def get_user_settings(session: AsyncSession, user_id: int) -> Dict[str, bool]:
        """Получение настроек пользователя"""
        result = await session.execute(select(User.toggle_schedule, User.all_semesters).where(User.user_id == user_id))
        settings = result.first()

        if not settings:
            return {"toggle_schedule": False, "all_semesters": False}

        return {"toggle_schedule": settings[0] or False, "all_semesters": settings[1] or False}

    @staticmethod
    async def get_user_ejournal_info(session: AsyncSession, user_id: int) -> List[str]:
        """Получение данных для электронного журнала"""
        result = await session.execute(
            select(User.ejournal_name, User.ejournal_password).where(User.user_id == user_id)
        )
        row = result.first()

        if not row or not row[0] or not row[1]:
            return []

        try:
            decrypted_fio = cipher.decrypt(row[0].encode()).decode()
            decrypted_pwd = cipher.decrypt(row[1].encode()).decode()

            if decrypted_fio == "None" or decrypted_pwd == "None":
                return []

            return [decrypted_fio, decrypted_pwd]
        except Exception:
            return []

    @staticmethod
    async def get_all_mentors(session: AsyncSession, toggle_schedule: bool = False) -> List[List[Any]]:
        """Получение всех преподавателей"""
        result = await session.execute(
            select(User.user_id, User.mentor_name).where(
                and_(User.user_status == "mentor", User.toggle_schedule == toggle_schedule)
            )
        )

        mentors = []
        for mentor_id, mentor_name in result.all():
            if mentor_id and mentor_name:
                mentors.append([mentor_id, mentor_name])

        return mentors

    @staticmethod
    async def get_mentor_name_by_id(
        session: AsyncSession, user_id: int, toggle_schedule: bool = False
    ) -> Optional[str]:
        """Получение имени преподавателя по ID"""
        result = await session.execute(
            select(User.mentor_name).where(
                and_(User.user_id == user_id, User.user_status == "mentor", User.toggle_schedule == toggle_schedule)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_setting(session: AsyncSession, user_id: int, setting: str, value: Any) -> None:
        """Обновление настройки пользователя"""
        await session.execute(update(User).where(User.user_id == user_id).values({setting: value}))
        await session.commit()

    @staticmethod
    async def update_user_theme(session: AsyncSession, user_id: int, theme: str) -> None:
        """Обновление темы пользователя"""
        await session.execute(update(User).where(User.user_id == user_id).values(user_theme=theme))
        await session.commit()

    @staticmethod
    async def update_ejournal_info(session: AsyncSession, user_id: int, fio: str, password: str) -> None:
        """Обновление данных электронного журнала"""
        encrypted_fio = cipher.encrypt(fio.encode())
        encrypted_password = cipher.encrypt(password.encode())

        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(ejournal_name=encrypted_fio.decode(), ejournal_password=encrypted_password.decode())
        )
        await session.commit()

    @staticmethod
    async def delete_ejournal_info(session: AsyncSession, user_id: int) -> None:
        """Удаление данных электронного журнала"""
        await session.execute(
            update(User).where(User.user_id == user_id).values(ejournal_name=None, ejournal_password=None)
        )
        await session.commit()

    @staticmethod
    async def delete_user(session: AsyncSession, user_id: int) -> None:
        """Удаление пользователя"""
        await session.execute(delete(User).where(User.user_id == user_id))
        await session.commit()
        print(f"👤 Пользователь удален 🗑️ | {user_id}")


class ChatRepository:
    """Репозиторий для работы с чатами (группами/супергруппами/каналами)"""

    @staticmethod
    async def create_or_update_chat(
        session: AsyncSession,
        chat_id: int,
        chat_type: str = "group",
    ) -> Chat:
        """Создание или обновление информации о чате"""
        try:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            chat = result.scalar_one_or_none()

            if chat:
                chat.chat_type = chat_type  # type: ignore
                print(f"💬 Чат обновлен 🔄 | ID: {chat_id}")
            else:
                chat = Chat(
                    chat_id=chat_id,
                    chat_type=chat_type,
                )
                session.add(chat)
                print(f"💬 Чат добавлен 🆕 | ID: {chat_id}")

            await session.commit()
            return chat

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при работе с чатом: {e}")
            raise

    @staticmethod
    async def get_chat_by_id(session: AsyncSession, chat_id: int) -> Optional[Chat]:
        """Получение чата по ID"""
        result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def chat_exists(session: AsyncSession, chat_id: int) -> bool:
        """Проверка существования чата"""
        result = await session.execute(select(func.count()).select_from(Chat).where(Chat.chat_id == chat_id))
        return result.scalar() > 0  # type: ignore

    @staticmethod
    async def subscribe_to_group(session: AsyncSession, chat_id: int, group_name: str) -> bool:
        """Подписка чата на группу студентов"""
        try:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            chat = result.scalar_one_or_none()

            if not chat:
                return False

            chat.subscribed_to_group = group_name  # type: ignore

            await session.commit()
            print(f"💬 Чат {chat_id} подписан на группу: {group_name}")
            return True

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при подписке чата на группу: {e}")
            return False

    @staticmethod
    async def subscribe_to_mentor(session: AsyncSession, chat_id: int, mentor_name: str) -> bool:
        """Подписка чата на преподавателя"""
        try:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            chat = result.scalar_one_or_none()

            if not chat:
                return False

            chat.subscribed_to_mentor = mentor_name  # type: ignore

            await session.commit()
            print(f"💬 Чат {chat_id} подписан на преподавателя: {mentor_name}")
            return True

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при подписке чата на преподавателя: {e}")
            return False

    @staticmethod
    async def unsubscribe(session: AsyncSession, chat_id: int) -> bool:
        """Отписка чата от всех подписок"""
        try:
            result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
            chat = result.scalar_one_or_none()

            if not chat:
                return False

            chat.subscribed_to_group = None  # type: ignore
            chat.subscribed_to_mentor = None  # type: ignore

            await session.commit()
            print(f"💬 Чат {chat_id} отписан от всех подписок")
            return True

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при отписке чата: {e}")
            return False

    @staticmethod
    async def update_chat_settings(
        session: AsyncSession,
        chat_id: int,
        send_daily: Optional[bool] = None,
        send_changes: Optional[bool] = None,
        theme: Optional[str] = None,
    ) -> bool:
        """Обновление настроек чата"""
        try:
            update_data = {}
            if send_daily is not None:
                update_data["send_daily"] = send_daily
            if send_changes is not None:
                update_data["send_changes"] = send_changes
            if theme is not None:
                update_data["theme"] = theme

            if not update_data:
                return False

            await session.execute(update(Chat).where(Chat.chat_id == chat_id).values(**update_data))
            await session.commit()
            print(f"💬 Настройки чата {chat_id} обновлены: {update_data}")
            return True

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при обновлении настроек чата: {e}")
            return False

    @staticmethod
    async def get_chats_subscribed_to_group(
        session: AsyncSession, group_name: str, only_active: bool = True
    ) -> List[Chat]:
        """Получение всех чатов, подписанных на группу"""
        conditions = [Chat.subscribed_to_group == group_name]

        if only_active:
            conditions.append(Chat.send_daily == True)

        result = await session.execute(select(Chat).where(and_(*conditions)))
        return list(result.scalars().all())

    @staticmethod
    async def get_chats_subscribed_to_mentor(
        session: AsyncSession, mentor_name: str, only_active: bool = True
    ) -> List[Chat]:
        """Получение всех чатов, подписанных на преподавателя"""
        conditions = [Chat.subscribed_to_mentor == mentor_name]

        if only_active:
            conditions.append(Chat.send_daily == True)

        result = await session.execute(select(Chat).where(and_(*conditions)))
        return list(result.scalars().all())

    @staticmethod
    async def get_all_subscribed_chats(session: AsyncSession) -> List[Chat]:
        """Получение всех чатов с активными подписками"""
        result = await session.execute(
            select(Chat).where(or_(Chat.subscribed_to_group.is_not(None), Chat.subscribed_to_mentor.is_not(None)))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_chats_for_daily_schedule(session: AsyncSession) -> List[Chat]:
        """Получение чатов для ежедневной рассылки"""
        result = await session.execute(
            select(Chat).where(
                and_(
                    Chat.send_daily == True,
                    or_(Chat.subscribed_to_group.is_not(None), Chat.subscribed_to_mentor.is_not(None)),
                )
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all_chats_with_subscriptions(session: AsyncSession) -> List[Dict[str, Any]]:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()

        chats_info = []
        for chat in chats:
            chats_info.append(
                {
                    "chat_id": chat.chat_id,
                    "subscribed_to_group": chat.subscribed_to_group,
                    "subscribed_to_mentor": chat.subscribed_to_mentor,
                    "send_daily": chat.send_daily,
                }
            )

        return chats_info

    @staticmethod
    async def get_chats_for_changes_schedule(session: AsyncSession) -> List[Chat]:
        """Получение чатов для рассылки изменений"""
        result = await session.execute(
            select(Chat).where(
                and_(
                    Chat.send_changes == True,
                    or_(Chat.subscribed_to_group.is_not(None), Chat.subscribed_to_mentor.is_not(None)),
                )
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_chat(session: AsyncSession, chat_id: int) -> bool:
        """Удаление чата из базы данных"""
        try:
            result = await session.execute(delete(Chat).where(Chat.chat_id == chat_id))
            await session.commit()

            if result.rowcount > 0:  # type: ignore
                print(f"💬 Чат удален 🗑️ | ID: {chat_id}")
                return True
            return False

        except SQLAlchemyError as e:
            await session.rollback()
            print(f"❌ Ошибка при удалении чата: {e}")
            return False

    @staticmethod
    async def get_chat_subscription_info(session: AsyncSession, chat_id: int) -> Dict[str, Any]:
        """Получение информации о подписке чата"""
        result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
        chat = result.scalar_one_or_none()

        if not chat:
            return {"exists": False}

        return {
            "exists": True,
            "chat_id": chat.chat_id,
            "chat_type": chat.chat_type,
            "subscribed_to_group": chat.subscribed_to_group,
            "subscribed_to_mentor": chat.subscribed_to_mentor,
            "send_daily": chat.send_daily,
            "send_changes": chat.send_changes,
            "theme": chat.theme,
            "created_at": chat.created_at,
        }


class ScheduleHashRepository:
    """Репозиторий для работы с хэшами расписаний"""

    @staticmethod
    async def check_and_update_hash(session: AsyncSession, group_name: str, date: date_type, hash_value: str) -> bool:
        """
        Проверяет и обновляет хэш.
        Возвращает True если хэш изменился, False если не изменился
        """
        # Ищем существующий хэш
        result = await session.execute(
            select(ScheduleHash).where(and_(ScheduleHash.group_name == group_name, ScheduleHash.date == date))
        )
        existing_hash = result.scalar_one_or_none()

        if not existing_hash:
            # Хэша нет, добавляем новый
            new_hash = ScheduleHash(group_name=group_name, date=date, hash_value=hash_value)
            session.add(new_hash)
            await session.commit()
            return False

        if existing_hash.hash_value != hash_value:  # type: ignore
            # Хэш изменился, обновляем
            existing_hash.hash_value = hash_value  # type: ignore
            await session.commit()
            return True

        return False

    @staticmethod
    async def cleanup_old_hashes(session: AsyncSession) -> None:
        """Удаление старых хэшей"""
        today = datetime.now().date()
        await session.execute(delete(ScheduleHash).where(ScheduleHash.date < today))
        await session.commit()
        print("#️⃣  Старые записи хэшей удалены 🗑️")


class ScheduleArchiveRepository:
    """Репозиторий для работы с архивом расписаний"""

    @staticmethod
    async def get_student_schedule(session: AsyncSession, date: str, group_name: str) -> List[Any]:
        """Получение расписания студентов"""
        result = await session.execute(
            select(ScheduleArchiveStudent.schedule).where(
                and_(ScheduleArchiveStudent.date == date, ScheduleArchiveStudent.group_name == group_name)
            )
        )
        row = result.scalar_one_or_none()

        if row:
            try:
                return ast.literal_eval(row)
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    async def get_mentor_schedule(session: AsyncSession, date: str, mentor_name: str) -> List[Any]:
        """Получение расписания преподавателей"""
        result = await session.execute(
            select(ScheduleArchiveMentor.schedule).where(
                and_(ScheduleArchiveMentor.date == date, ScheduleArchiveMentor.mentor_name == mentor_name)
            )
        )
        row = result.scalar_one_or_none()

        if row:
            try:
                return ast.literal_eval(row)
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    async def update_student_schedule(
        session: AsyncSession, date: str, group_name: str, schedule: List[Any], schedule_hash: str
    ) -> None:
        """Обновление расписания студентов"""
        # Проверяем существование записи
        result = await session.execute(
            select(ScheduleArchiveStudent).where(
                and_(ScheduleArchiveStudent.date == date, ScheduleArchiveStudent.group_name == group_name)
            )
        )
        existing = result.scalar_one_or_none()

        schedule_str = str(schedule)

        if existing:
            # Обновляем существующую запись
            existing.schedule = schedule_str  # type: ignore
            existing.schedule_hash = schedule_hash  # type: ignore
        else:
            # Создаем новую запись
            new_record = ScheduleArchiveStudent(
                date=date, group_name=group_name, schedule=schedule_str, schedule_hash=schedule_hash
            )
            session.add(new_record)

        await session.commit()

    @staticmethod
    async def update_mentor_schedule(
        session: AsyncSession, date: str, mentor_name: str, schedule: List[Any], schedule_hash: str
    ) -> None:
        """Обновление расписания преподавателей"""
        # Проверяем существование записи
        result = await session.execute(
            select(ScheduleArchiveMentor).where(
                and_(ScheduleArchiveMentor.date == date, ScheduleArchiveMentor.mentor_name == mentor_name)
            )
        )
        existing = result.scalar_one_or_none()

        schedule_str = str(schedule)

        if existing:
            # Обновляем существующую запись
            existing.schedule = schedule_str  # type: ignore
            existing.schedule_hash = schedule_hash  # type: ignore
        else:
            # Создаем новую запись
            new_record = ScheduleArchiveMentor(
                date=date, mentor_name=mentor_name, schedule=schedule_str, schedule_hash=schedule_hash
            )
            session.add(new_record)

        await session.commit()


db_manager = DatabaseManager()
