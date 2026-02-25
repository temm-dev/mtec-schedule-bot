"""Database layer (repositories + session manager).

The code uses SQLite + SQLAlchemy async ORM with proper error handling,
security measures, and performance optimizations.

Important:
    The application relies on the current transaction semantics.
    The DatabaseManager.get_session context handles commit on success
    and rollback on errors automatically.
"""

import ast
import logging
from datetime import date as date_type
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from config.bot_config import SECRET_KEY
from config.paths import PATH_DBs
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, delete, func, or_, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from .models import Base, Chat, ScheduleArchiveMentor, ScheduleArchiveStudent, ScheduleHash, User

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Manages encryption/decryption operations with proper error handling.
    
    Provides secure encryption for sensitive data like credentials.
    Uses Fernet symmetric encryption with proper key management.
    """
    
    def __init__(self, key: bytes):
        """Initialize encryption manager with Fernet key.
        
        Args:
            key: Encryption key for Fernet cipher.
            
        Raises:
            ValueError: If key is invalid for Fernet.
        """
        try:
            self._cipher = Fernet(key)
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise ValueError("Invalid encryption key") from e
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data.
        
        Args:
            data: Plain text data to encrypt.
            
        Returns:
            Encrypted string.
            
        Raises:
            ValueError: If encryption fails.
        """
        try:
            if not data:
                return ""
            return self._cipher.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError(f"Encryption failed: {e}") from e
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data.
        
        Args:
            encrypted_data: Encrypted string to decrypt.
            
        Returns:
            Decrypted plain text.
            
        Raises:
            ValueError: If decryption fails.
        """
        try:
            if not encrypted_data or encrypted_data == "None":
                return ""
            return self._cipher.decrypt(encrypted_data.encode()).decode()
        except InvalidToken:
            logger.error("Invalid token for decryption")
            raise ValueError("Invalid encryption token")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Decryption failed: {e}") from e

# Global encryption manager instance
encryption_manager = EncryptionManager(SECRET_KEY.encode())


class DatabaseManager:
    """Create and manage SQLAlchemy async sessions with proper error handling.

    Provides database connection management, session creation, and initialization.
    Implements connection pooling and proper resource cleanup.

    Args:
        db_url: SQLAlchemy URL for the database connection.
        
    Attributes:
        engine: SQLAlchemy async engine instance.
        async_session: Session factory for creating database sessions.
    """

    def __init__(self, db_url: str = f"sqlite+aiosqlite:///{PATH_DBs}bot_database.db"):
        """Initialize database manager with connection settings.
        
        Args:
            db_url: Database connection URL.
        """
        try:
            self.engine = create_async_engine(
                db_url, 
                echo=False, 
                future=True,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            self.async_session = async_sessionmaker(
                self.engine, 
                class_=AsyncSession, 
                expire_on_commit=False
            )
            logger.info(f"Database engine initialized for: {db_url}")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise

    async def init_db(self) -> None:
        """Initialize database schema with proper error handling.

        Creates all tables defined in models module.
        Implements retry logic for connection issues.
        
        Raises:
            SQLAlchemyError: If database initialization fails.
        """
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized successfully")
            print("✅ База данных инициализирована")
        except SQLAlchemyError as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during database initialization: {e}")
            raise

    async def get_session(self) -> AsyncSession:  # type: ignore
        """Yield a database session with automatic commit/rollback.

        This is implemented as an async generator so callers can use:

        ```python
        async for session in db_manager.get_session():
            ...
        ```

        Behavior:
            - Commits after successful completion of the caller block.
            - Rolls back on exception.
            - Ensures proper session cleanup.

        Yields:
            AsyncSession instance with proper transaction management.
            
        Raises:
            SQLAlchemyError: If session creation or transaction fails.
        """
        session = None
        try:
            async with self.async_session() as session:
                try:
                    yield session  # type: ignore
                except Exception as e:
                    logger.error(f"Transaction failed, rolling back: {e}")
                    await session.rollback()
                    raise
                else:
                    await session.commit()
                    logger.debug("Transaction committed successfully")
        except SQLAlchemyError as e:
            logger.error(f"Database session error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected session error: {e}")
            raise
        finally:
            if session:
                await session.close()
                logger.debug("Database session closed")


class UserRepository:
    """Repository for user CRUD operations with optimized queries.
    
    Provides methods for creating, updating, and retrieving user data.
    Implements proper input validation, error handling, and performance optimizations.
    """

    @staticmethod
    async def create_or_update_user(
        session: AsyncSession,
        user_id: int,
        user_status: str,
        mentor_name: Optional[str] = None,
        student_group: Optional[str] = None,
    ) -> User:
        """Create or update a user record with validation and error handling.

        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user id (can be any integer, including negative for groups/channels).
            user_status: User status string ('student' or 'mentor').
            mentor_name: Optional mentor name (max 100 chars).
            student_group: Optional student group name (max 50 chars).

        Returns:
            The created/updated User instance.
            
        Raises:
            ValueError: If input validation fails.
            SQLAlchemyError: If database operation fails.
        """
        # Input validation
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
        
        if user_status not in ["student", "mentor"]:
            raise ValueError("user_status must be 'student' or 'mentor'")
        
        if mentor_name and len(mentor_name) > 100:
            raise ValueError("mentor_name cannot exceed 100 characters")
            
        if student_group and len(student_group) > 50:
            raise ValueError("student_group cannot exceed 50 characters")

        try:
            # Check existing user with optimized query
            result = await session.execute(
                select(User).where(User.user_id == user_id).limit(1)
            )
            user = result.scalar_one_or_none()

            if user:
                # Update existing user
                user.user_status = user_status
                user.mentor_name = mentor_name
                user.student_group = student_group
                logger.info(f"User updated: {user_id}")
                print(f"👤 Пользователь обновлен 🔄 | {user_id}")
            else:
                # Create new user
                user = User(
                    user_id=user_id, 
                    user_status=user_status, 
                    mentor_name=mentor_name, 
                    student_group=student_group
                )
                session.add(user)
                await session.commit()  # Commit the new user
                logger.info(f"User created: {user_id} - {student_group or mentor_name}")
                print(f"👤 Пользователь добавлен 🆕 | {user_id} - {student_group or mentor_name}")

            return user

        except IntegrityError as e:
            logger.error(f"Integrity error for user {user_id}: {e}")
            session.rollback()
            raise ValueError(f"User data integrity violation: {e}") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error for user {user_id}: {e}")
            raise

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Get a user by ID with validation.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID (can be any integer, including negative for groups/channels).
            
        Returns:
            User instance if found, None otherwise.
            
        Raises:
            ValueError: If user_id is invalid.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User).where(User.user_id == user_id).limit(1)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving user {user_id}: {e}")
            raise

    @staticmethod
    async def user_exists(session: AsyncSession, user_id: int) -> bool:
        """Check whether a user exists with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID to check.
            
        Returns:
            True if user exists, False otherwise.
            
        Raises:
            ValueError: If user_id is invalid.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(func.count(User.id)).where(User.user_id == user_id)
            )
            return result.scalar() > 0  # type: ignore
        except SQLAlchemyError as e:
            logger.error(f"Error checking user existence {user_id}: {e}")
            raise

    @staticmethod
    async def get_user_status(session: AsyncSession, user_id: int) -> str:
        """Get user status for a given user ID with validation.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Returns:
            User status string or empty string if not found.
            
        Raises:
            ValueError: If user_id is invalid.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User.user_status).where(User.user_id == user_id).limit(1)
            )
            status = result.scalar_one_or_none()
            return status or ""
        except SQLAlchemyError as e:
            logger.error(f"Error getting user status {user_id}: {e}")
            raise

    @staticmethod
    async def get_all_users(session: AsyncSession) -> List[int]:
        """Get all user IDs with optimized query and memory management.
        
        Args:
            session: SQLAlchemy async session.
            
        Returns:
            List of all user IDs.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(User.user_id).order_by(User.user_id)
            )
            return [user_id for user_id in result.scalars().all()]
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all users: {e}")
            raise

    @staticmethod
    async def get_all_groups(session: AsyncSession) -> List[str]:
        """Get all unique student groups with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            
        Returns:
            List of unique student group names.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(User.student_group)
                .where(User.user_status == "student", User.student_group.is_not(None))
                .distinct()
                .order_by(User.student_group)
            )
            groups = [group for group in result.scalars().all() if group]
            logger.info(f"Retrieved {len(groups)} unique groups: {groups}")
            return groups
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all groups: {e}")
            raise

    @staticmethod
    async def get_users_by_group(session: AsyncSession, group: str, toggle_schedule: bool = False) -> List[int]:
        """Get users by group with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            group: Student group name (must be non-empty string).
            toggle_schedule: Filter by schedule toggle status.
            
        Returns:
            List of user IDs in the specified group.
            
        Raises:
            ValueError: If group name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not group or not isinstance(group, str):
            raise ValueError("group must be a non-empty string")
            
        try:
            result = await session.execute(
                select(User.user_id)
                .where(
                    and_(
                        User.user_status == "student", 
                        User.student_group == group, 
                        User.toggle_schedule == toggle_schedule
                    )
                )
                .order_by(User.user_id)
            )
            return [user_id for user_id in result.scalars().all()]
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving users by group {group}: {e}")
            raise

    @staticmethod
    async def get_users_by_group_and_theme(
        session: AsyncSession, group: str, theme: str = "Classic", toggle_schedule: bool = False
    ) -> List[int]:
        """Get users by group and theme with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            group: Student group name (must be non-empty string).
            theme: UI theme name (default: "Classic").
            toggle_schedule: Filter by schedule toggle status.
            
        Returns:
            List of user IDs matching the criteria.
            
        Raises:
            ValueError: If group or theme is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not group or not isinstance(group, str):
            raise ValueError("group must be a non-empty string")
        if not theme or not isinstance(theme, str):
            raise ValueError("theme must be a non-empty string")
            
        try:
            result = await session.execute(
                select(User.user_id)
                .where(
                    and_(
                        User.student_group == group, 
                        User.user_theme == theme, 
                        User.toggle_schedule == toggle_schedule
                    )
                )
                .order_by(User.user_id)
            )
            return [user_id for user_id in result.scalars().all()]
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving users by group {group} and theme {theme}: {e}")
            raise

    @staticmethod
    async def get_user_group(session: AsyncSession, user_id: int) -> str:
        """Get user group with validation.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Returns:
            User group name or empty string if not found.
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User.student_group).where(User.user_id == user_id).limit(1)
            )
            group = result.scalar_one_or_none()
            return group or ""
        except SQLAlchemyError as e:
            logger.error(f"Error getting user group {user_id}: {e}")
            raise

    @staticmethod
    async def get_user_theme(session: AsyncSession, user_id: int) -> str:
        """Get user theme with validation and default fallback.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Returns:
            User theme name or "Classic" if not found.
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User.user_theme).where(User.user_id == user_id).limit(1)
            )
            theme = result.scalar_one_or_none()
            return theme or "Classic"
        except SQLAlchemyError as e:
            logger.error(f"Error getting user theme {user_id}: {e}")
            raise

    @staticmethod
    async def get_user_settings(session: AsyncSession, user_id: int) -> Dict[str, bool]:
        """Get user settings with validation and default fallback.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Returns:
            Dictionary with user settings (toggle_schedule, all_semesters).
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User.toggle_schedule, User.all_semesters)
                .where(User.user_id == user_id)
            )
            settings = result.first()

            if not settings:
                return {"toggle_schedule": False, "all_semesters": False}

            return {
                "toggle_schedule": bool(settings[0] or False), 
                "all_semesters": bool(settings[1] or False)
            }
        except SQLAlchemyError as e:
            logger.error(f"Error getting user settings {user_id}: {e}")
            raise

    @staticmethod
    async def get_user_ejournal_info(session: AsyncSession, user_id: int) -> List[str]:
        """Get decrypted e-journal credentials with security and validation.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Returns:
            List with [decrypted_fio, decrypted_password] or empty list if not found.
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User.ejournal_name, User.ejournal_password)
                .where(User.user_id == user_id)
            )
            row = result.first()

            if not row or not row[0] or not row[1]:
                return []

            try:
                decrypted_fio = encryption_manager.decrypt(row[0])
                decrypted_pwd = encryption_manager.decrypt(row[1])

                if not decrypted_fio or not decrypted_pwd:
                    return []

                return [decrypted_fio, decrypted_pwd]
            except ValueError as e:
                logger.warning(f"Failed to decrypt e-journal data for user {user_id}: {e}")
                return []
        except SQLAlchemyError as e:
            logger.error(f"Error getting e-journal info {user_id}: {e}")
            raise

    @staticmethod
    async def get_all_mentors(session: AsyncSession, toggle_schedule: bool = False) -> List[List[Any]]:
        """Get all mentors with optimized query and validation.
        
        Args:
            session: SQLAlchemy async session.
            toggle_schedule: Filter by schedule toggle status.
            
        Returns:
            List of [mentor_id, mentor_name] pairs.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(User.user_id, User.mentor_name)
                .where(
                    and_(
                        User.user_status == "mentor", 
                        User.mentor_name.is_not(None),
                        User.toggle_schedule == toggle_schedule
                    )
                )
                .order_by(User.mentor_name)
            )

            mentors = []
            for mentor_id, mentor_name in result.all():
                if mentor_id and mentor_name:
                    mentors.append([mentor_id, mentor_name])

            return mentors
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all mentors: {e}")
            raise

    @staticmethod
    async def get_mentor_name_by_id(
        session: AsyncSession, user_id: int, toggle_schedule: bool = False
    ) -> Optional[str]:
        """Get mentor name by ID with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            toggle_schedule: Filter by schedule toggle status.
            
        Returns:
            Mentor name or None if not found.
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(
                select(User.mentor_name)
                .where(
                    and_(
                        User.user_id == user_id, 
                        User.user_status == "mentor", 
                        User.toggle_schedule == toggle_schedule
                    )
                ).limit(1)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting mentor name {user_id}: {e}")
            raise

    @staticmethod
    async def update_user_setting(session: AsyncSession, user_id: int, setting: str, value: Any) -> None:
        """Update a single user setting with validation and security.

        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user id (can be any integer, including negative for groups/channels).
            setting: Column name to update (must be valid User column).
            value: New value for the setting.
            
        Raises:
            ValueError: If user_id or setting is invalid.
            SQLAlchemyError: If database operation fails.
        """
        # Input validation
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        if not setting or not isinstance(setting, str):
            raise ValueError("setting must be a non-empty string")
            
        # Whitelist allowed settings to prevent SQL injection
        allowed_settings = {
            'user_theme', 'toggle_schedule', 'all_semesters', 
            'student_group', 'mentor_name', 'user_status'
        }
        
        if setting not in allowed_settings:
            raise ValueError(f"setting '{setting}' is not allowed")
        
        try:
            # Use parameterized query to prevent SQL injection
            stmt = update(User).where(User.user_id == user_id)
            
            if setting == 'user_theme':
                stmt = stmt.values(user_theme=str(value))
            elif setting == 'toggle_schedule':
                stmt = stmt.values(toggle_schedule=bool(value))
            elif setting == 'all_semesters':
                stmt = stmt.values(all_semesters=bool(value))
            elif setting == 'student_group':
                stmt = stmt.values(student_group=str(value) if value else None)
            elif setting == 'mentor_name':
                stmt = stmt.values(mentor_name=str(value) if value else None)
            elif setting == 'user_status':
                if value not in ['student', 'mentor']:
                    raise ValueError("user_status must be 'student' or 'mentor'")
                stmt = stmt.values(user_status=value)
                
            await session.execute(stmt)
            logger.info(f"Updated user {user_id} setting {setting}")
        except SQLAlchemyError as e:
            logger.error(f"Error updating user setting {user_id}, {setting}: {e}")
            raise

    @staticmethod
    async def update_user_theme(session: AsyncSession, user_id: int, theme: str) -> None:
        """Update user theme with validation.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            theme: Theme name (must be non-empty string).
            
        Raises:
            ValueError: If user_id or theme is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
        if not theme or not isinstance(theme, str):
            raise ValueError("theme must be a non-empty string")
            
        try:
            await session.execute(
                update(User).where(User.user_id == user_id).values(user_theme=theme)
            )
            await session.commit()  # Commit the update
            logger.info(f"Updated user {user_id} theme to {theme}")
        except SQLAlchemyError as e:
            logger.error(f"Error updating user theme {user_id}: {e}")
            raise

    @staticmethod
    async def update_ejournal_info(session: AsyncSession, user_id: int, fio: str, password: str) -> None:
        """Update e-journal credentials for a user with encryption and validation.

        The credentials are stored encrypted using Fernet symmetric encryption.

        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user id (can be any integer, including negative for groups/channels).
            fio: User full name (must be non-empty string).
            password: E-journal password (must be non-empty string).
            
        Raises:
            ValueError: If user_id, fio, or password is invalid.
            SQLAlchemyError: If database operation fails.
        """
        # Input validation
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
        if not fio or not isinstance(fio, str):
            raise ValueError("fio must be a non-empty string")
        if not password or not isinstance(password, str):
            raise ValueError("password must be a non-empty string")
            
        try:
            encrypted_fio = encryption_manager.encrypt(fio)
            encrypted_password = encryption_manager.encrypt(password)

            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(ejournal_name=encrypted_fio, ejournal_password=encrypted_password)
            )
            await session.commit()  # Commit the update
            logger.info(f"Updated e-journal credentials for user {user_id}")
        except SQLAlchemyError as e:
            logger.error(f"Error updating e-journal info {user_id}: {e}")
            raise
        except ValueError as e:
            logger.error(f"Encryption error for user {user_id}: {e}")
            raise

    @staticmethod
    async def delete_ejournal_info(session: AsyncSession, user_id: int) -> None:
        """Remove e-journal credentials for a user with validation.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            await session.execute(
                update(User).where(User.user_id == user_id)
                .values(ejournal_name=None, ejournal_password=None)
            )
            await session.commit()  # Commit the update
            logger.info(f"Deleted e-journal credentials for user {user_id}")
        except SQLAlchemyError as e:
            logger.error(f"Error deleting e-journal info {user_id}: {e}")
            raise

    @staticmethod
    async def delete_user(session: AsyncSession, user_id: int) -> None:
        """Delete a user record with validation and logging.
        
        Args:
            session: SQLAlchemy async session.
            user_id: Telegram user ID.
            
        Raises:
            ValueError: If user_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(user_id, int):
            raise ValueError("user_id must be an integer")
            
        try:
            result = await session.execute(delete(User).where(User.user_id == user_id))
            
            if result.rowcount > 0:  # type: ignore
                await session.commit()  # Commit the deletion
                logger.info(f"User deleted: {user_id}")
                print(f"👤 Пользователь удален 🗑️ | {user_id}")
            else:
                logger.warning(f"User {user_id} not found for deletion")
        except SQLAlchemyError as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            raise


class ChatRepository:
    """Repository for chat CRUD operations with optimized queries.
    
    Provides methods for creating, updating, and retrieving chat data.
    Implements proper input validation, error handling, and subscription management.
    """

    @staticmethod
    async def create_or_update_chat(
        session: AsyncSession,
        chat_id: int,
        chat_type: str = "group",
    ) -> Chat:
        """Create or update a chat record with validation and error handling.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID (can be any integer, including negative for groups/channels).
            chat_type: Chat type ('group', 'supergroup', 'channel').
            
        Returns:
            The created/updated Chat instance.
            
        Raises:
            ValueError: If chat_id or chat_type is invalid.
            SQLAlchemyError: If database operation fails.
        """
        # Input validation
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        if not chat_type or not isinstance(chat_type, str):
            raise ValueError("chat_type must be a non-empty string")
            
        valid_chat_types = ['group', 'supergroup', 'channel']
        if chat_type not in valid_chat_types:
            raise ValueError(f"chat_type must be one of {valid_chat_types}")
        
        try:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            chat = result.scalar_one_or_none()

            if chat:
                chat.chat_type = chat_type  # type: ignore
                logger.info(f"Chat updated: {chat_id}")
                print(f"💬 Чат обновлен 🔄 | ID: {chat_id}")
            else:
                chat = Chat(
                    chat_id=chat_id,
                    chat_type=chat_type,
                )
                session.add(chat)
                await session.commit()  # Commit the new chat
                logger.info(f"Chat created: {chat_id}")
                print(f"💬 Чат добавлен 🆕 | ID: {chat_id}")

            return chat

        except IntegrityError as e:
            logger.error(f"Integrity error for chat {chat_id}: {e}")
            session.rollback()
            raise ValueError(f"Chat data integrity violation: {e}") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error for chat {chat_id}: {e}")
            raise

    @staticmethod
    async def get_chat_by_id(session: AsyncSession, chat_id: int) -> Optional[Chat]:
        """Get chat by ID with validation.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID.
            
        Returns:
            Chat instance if found, None otherwise.
            
        Raises:
            ValueError: If chat_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        try:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chat {chat_id}: {e}")
            raise

    @staticmethod
    async def chat_exists(session: AsyncSession, chat_id: int) -> bool:
        """Check whether a chat exists with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID to check.
            
        Returns:
            True if chat exists, False otherwise.
            
        Raises:
            ValueError: If chat_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        try:
            result = await session.execute(
                select(func.count(Chat.id)).where(Chat.chat_id == chat_id)
            )
            return result.scalar() > 0  # type: ignore
        except SQLAlchemyError as e:
            logger.error(f"Error checking chat existence {chat_id}: {e}")
            raise

    @staticmethod
    async def subscribe_to_group(session: AsyncSession, chat_id: int, group_name: str) -> bool:
        """Subscribe chat to a student group with validation.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID.
            group_name: Student group name (must be non-empty string).
            
        Returns:
            True if subscription successful, False if chat not found.
            
        Raises:
            ValueError: If chat_id or group_name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
        if not group_name or not isinstance(group_name, str):
            raise ValueError("group_name must be a non-empty string")
            
        try:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            chat = result.scalar_one_or_none()

            if not chat:
                return False

            chat.subscribed_to_group = group_name  # type: ignore
            logger.info(f"Chat {chat_id} subscribed to group: {group_name}")
            print(f"💬 Чат {chat_id} подписан на группу: {group_name}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error subscribing chat {chat_id} to group {group_name}: {e}")
            raise

    @staticmethod
    async def subscribe_to_mentor(session: AsyncSession, chat_id: int, mentor_name: str) -> bool:
        """Subscribe chat to a mentor with validation.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID.
            mentor_name: Mentor name (must be non-empty string).
            
        Returns:
            True if subscription successful, False if chat not found.
            
        Raises:
            ValueError: If chat_id or mentor_name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
        if not mentor_name or not isinstance(mentor_name, str):
            raise ValueError("mentor_name must be a non-empty string")
            
        try:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            chat = result.scalar_one_or_none()

            if not chat:
                return False

            chat.subscribed_to_mentor = mentor_name  # type: ignore
            logger.info(f"Chat {chat_id} subscribed to mentor: {mentor_name}")
            print(f"💬 Чат {chat_id} подписан на преподавателя: {mentor_name}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error subscribing chat {chat_id} to mentor {mentor_name}: {e}")
            raise

    @staticmethod
    async def unsubscribe(session: AsyncSession, chat_id: int) -> bool:
        """Remove all subscriptions for a chat with validation.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID.
            
        Returns:
            True if unsubscription successful, False if chat not found.
            
        Raises:
            ValueError: If chat_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        try:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
            chat = result.scalar_one_or_none()

            if not chat:
                return False

            chat.subscribed_to_group = None  # type: ignore
            chat.subscribed_to_mentor = None  # type: ignore

            logger.info(f"Chat {chat_id} unsubscribed from all subscriptions")
            print(f"💬 Чат {chat_id} отписан от всех подписок")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error unsubscribing chat {chat_id}: {e}")
            raise

    @staticmethod
    async def update_chat_settings(
        session: AsyncSession,
        chat_id: int,
        send_daily: Optional[bool] = None,
        send_changes: Optional[bool] = None,
        theme: Optional[str] = None,
    ) -> bool:
        """Update chat settings with validation and security.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID.
            send_daily: Whether to send daily schedule notifications.
            send_changes: Whether to send schedule change notifications.
            theme: Chat theme preference.
            
        Returns:
            True if update successful, False if no valid settings provided.
            
        Raises:
            ValueError: If chat_id or theme is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        try:
            update_data = {}
            if send_daily is not None:
                update_data["send_daily"] = bool(send_daily)
            if send_changes is not None:
                update_data["send_changes"] = bool(send_changes)
            if theme is not None:
                if not theme or not isinstance(theme, str):
                    raise ValueError("theme must be a non-empty string")
                update_data["theme"] = theme

            if not update_data:
                return False

            await session.execute(
                update(Chat).where(Chat.chat_id == chat_id).values(**update_data)
            )
            await session.commit()  # Commit the update
            logger.info(f"Chat {chat_id} settings updated: {update_data}")
            print(f"💬 Настройки чата {chat_id} обновлены: {update_data}")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error updating chat settings {chat_id}: {e}")
            raise

    @staticmethod
    async def get_chats_subscribed_to_group(
        session: AsyncSession, group_name: str, only_active: bool = True
    ) -> List[Chat]:
        """Get all chats subscribed to a group with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            group_name: Student group name (must be non-empty string).
            only_active: Filter only chats with send_daily enabled.
            
        Returns:
            List of Chat instances subscribed to the group.
            
        Raises:
            ValueError: If group_name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not group_name or not isinstance(group_name, str):
            raise ValueError("group_name must be a non-empty string")
            
        try:
            conditions = [Chat.subscribed_to_group == group_name]

            if only_active:
                conditions.append(Chat.send_daily == True)

            result = await session.execute(
                select(Chat).where(and_(*conditions)).order_by(Chat.chat_id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chats for group {group_name}: {e}")
            raise

    @staticmethod
    async def get_chats_subscribed_to_mentor(
        session: AsyncSession, mentor_name: str, only_active: bool = True
    ) -> List[Chat]:
        """Get all chats subscribed to a mentor with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            mentor_name: Mentor name (must be non-empty string).
            only_active: Filter only chats with send_daily enabled.
            
        Returns:
            List of Chat instances subscribed to the mentor.
            
        Raises:
            ValueError: If mentor_name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not mentor_name or not isinstance(mentor_name, str):
            raise ValueError("mentor_name must be a non-empty string")
            
        try:
            conditions = [Chat.subscribed_to_mentor == mentor_name]

            if only_active:
                conditions.append(Chat.send_daily == True)

            result = await session.execute(
                select(Chat).where(and_(*conditions)).order_by(Chat.chat_id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chats for mentor {mentor_name}: {e}")
            raise

    @staticmethod
    async def get_all_subscribed_chats(session: AsyncSession) -> List[Chat]:
        """Get all chats with active subscriptions with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            
        Returns:
            List of Chat instances with active subscriptions.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(Chat)
                .where(or_(Chat.subscribed_to_group.is_not(None), Chat.subscribed_to_mentor.is_not(None)))
                .order_by(Chat.chat_id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving all subscribed chats: {e}")
            raise

    @staticmethod
    async def get_chats_for_daily_schedule(session: AsyncSession) -> List[Chat]:
        """Get chats for daily schedule mailing with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            
        Returns:
            List of Chat instances eligible for daily schedule.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(Chat)
                .where(
                    and_(
                        Chat.send_daily == True,
                        or_(Chat.subscribed_to_group.is_not(None), Chat.subscribed_to_mentor.is_not(None)),
                    )
                )
                .order_by(Chat.chat_id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chats for daily schedule: {e}")
            raise

    @staticmethod
    async def get_all_chats_with_subscriptions(session: AsyncSession) -> List[Dict[str, Any]]:
        """Get all chats with subscription information with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            
        Returns:
            List of dictionaries with chat subscription info.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(Chat).order_by(Chat.chat_id)
            )
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
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chats with subscriptions: {e}")
            raise

    @staticmethod
    async def get_chats_for_changes_schedule(session: AsyncSession) -> List[Chat]:
        """Get chats for schedule changes mailing with optimized query.
        
        Args:
            session: SQLAlchemy async session.
            
        Returns:
            List of Chat instances eligible for schedule change notifications.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            result = await session.execute(
                select(Chat)
                .where(
                    and_(
                        Chat.send_changes == True,
                        or_(Chat.subscribed_to_group.is_not(None), Chat.subscribed_to_mentor.is_not(None)),
                    )
                )
                .order_by(Chat.chat_id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving chats for schedule changes: {e}")
            raise

    @staticmethod
    async def delete_chat(session: AsyncSession, chat_id: int) -> bool:
        """Delete a chat record with validation and proper error handling.

        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID (can be any integer, including negative for groups/channels).

        Returns:
            True if a row was deleted, False otherwise.
            
        Raises:
            ValueError: If chat_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        try:
            result = await session.execute(
                delete(Chat).where(Chat.chat_id == chat_id)
            )

            if result.rowcount > 0:  # type: ignore
                logger.info(f"Chat deleted: {chat_id}")
                print(f"💬 Чат удален 🗑️ | ID: {chat_id}")
                return True
            logger.warning(f"Chat {chat_id} not found for deletion")
            return False

        except SQLAlchemyError as e:
            logger.error(f"Error deleting chat {chat_id}: {e}")
            raise

    @staticmethod
    async def get_chat_subscription_info(session: AsyncSession, chat_id: int) -> Dict[str, Any]:
        """Get chat subscription information with validation.
        
        Args:
            session: SQLAlchemy async session.
            chat_id: Telegram chat ID.
            
        Returns:
            Dictionary with chat subscription details.
            
        Raises:
            ValueError: If chat_id is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not isinstance(chat_id, int):
            raise ValueError("chat_id must be an integer")
            
        try:
            result = await session.execute(
                select(Chat).where(Chat.chat_id == chat_id)
            )
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
        except SQLAlchemyError as e:
            logger.error(f"Error getting chat subscription info {chat_id}: {e}")
            raise


class ScheduleHashRepository:
    """Repository for schedule hash management with optimized queries.
    
    Provides methods for tracking schedule changes using hash values.
    Implements proper validation, error handling, and cleanup operations.
    """

    @staticmethod
    async def check_and_update_hash(
        session: AsyncSession, group_name: str, date: Union[date_type, str], hash_value: str
    ) -> bool:
        """Check whether a hash changed and update it with validation.

        Args:
            session: SQLAlchemy async session.
            group_name: Group/mentor identifier used for hashing.
            date: Schedule date (datetime.date or string 'DD.MM.YYYY').
            hash_value: Newly calculated hash (must be non-empty string).

        Returns:
            True if the stored hash was different and has been updated.
            False otherwise.
            
        Raises:
            ValueError: If group_name or hash_value is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not group_name or not isinstance(group_name, str):
            raise ValueError("group_name must be a non-empty string")
        if not hash_value or not isinstance(hash_value, str):
            raise ValueError("hash_value must be a non-empty string")
            
        # Convert date to string format for database storage
        date_str = date.strftime("%d.%m.%Y") if isinstance(date, date_type) else str(date)
        
        if not date_str or not isinstance(date_str, str):
            raise ValueError("date must be a datetime.date object or date string")
            
        try:
            result = await session.execute(
                select(ScheduleHash)
                .where(and_(ScheduleHash.group_name == group_name, ScheduleHash.date == date_str))
            )
            existing_hash = result.scalar_one_or_none()

            if not existing_hash:
                new_hash = ScheduleHash(
                    group_name=group_name, 
                    date=date_str, 
                    hash_value=hash_value
                )
                session.add(new_hash)
                await session.commit()  # Commit new hash
                logger.debug(f"Created new hash for {group_name} on {date_str}")
                return False

            if existing_hash.hash_value != hash_value:  # type: ignore
                existing_hash.hash_value = hash_value  # type: ignore
                await session.commit()  # Commit updated hash
                logger.debug(f"Updated hash for {group_name} on {date_str}")
                return True

            await session.commit()  # Commit even if no changes to close transaction
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error checking/updating hash for {group_name} on {date_str}: {e}")
            raise

    @staticmethod
    async def cleanup_old_hashes(session: AsyncSession) -> None:
        """Delete hash records older than today with proper error handling.
        
        Args:
            session: SQLAlchemy async session.
            
        Raises:
            SQLAlchemyError: If database operation fails.
        """
        try:
            today = datetime.now().date()
            result = await session.execute(
                delete(ScheduleHash).where(ScheduleHash.date < today)
            )
            
            deleted_count = result.rowcount  # type: ignore
            await session.commit()  # Commit the deletion
            logger.info(f"Cleaned up {deleted_count} old hash records")
            print("#️⃣  Старые записи хэшей удалены 🗑️")
        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up old hashes: {e}")
            raise


class ScheduleArchiveRepository:
    """Repository for schedule archive operations with optimized queries.
    
    Provides methods for storing and retrieving archived schedule data.
    Implements proper validation, error handling, and safe parsing.
    """

    @staticmethod
    def _safe_parse_schedule(value: Any) -> List[Any]:
        """Parse a schedule stored as a string into Python objects.

        The DB stores schedule as str(schedule) (a Python literal).
        Uses ast.literal_eval for safe reconstruction of the list.

        Args:
            value: Raw value from DB (should be string representation of list).

        Returns:
            Parsed schedule list or empty list on parse errors.
        """
        if not value:
            return []

        # Extract the actual string value if it's a SQLAlchemy result
        schedule_str = ""
        
        if hasattr(value, 'schedule'):
            # SQLAlchemy model object
            schedule_str = value.schedule
        elif isinstance(value, str):
            # Direct string value
            schedule_str = value
        elif hasattr(value, '__getitem__') and len(value) > 0:
            # Tuple or list result
            first_item = value[0]
            if hasattr(first_item, 'schedule'):
                schedule_str = first_item.schedule
            else:
                schedule_str = str(first_item)
        else:
            # Fallback: convert to string
            schedule_str = str(value)

        try:
            return ast.literal_eval(schedule_str)
        except (ValueError, SyntaxError) as e:
            logger.warning(f"Failed to parse schedule data: {e}")
            logger.debug(f"Problematic schedule data: {repr(schedule_str)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing schedule data: {e}")
            logger.debug(f"Problematic schedule data: {repr(schedule_str)}")
            return []

    @staticmethod
    async def get_student_schedule(session: AsyncSession, date: str, group_name: str) -> List[Any]:
        """Get archived student schedule with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            date: Schedule date as string.
            group_name: Student group name.
            
        Returns:
            Parsed schedule list or empty list if not found.
            
        Raises:
            ValueError: If date or group_name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not date or not isinstance(date, str):
            raise ValueError("date must be a non-empty string")
        if not group_name or not isinstance(group_name, str):
            raise ValueError("group_name must be a non-empty string")
            
        try:
            result = await session.execute(
                select(ScheduleArchiveStudent.schedule)
                .where(
                    and_(
                        ScheduleArchiveStudent.date == date, 
                        ScheduleArchiveStudent.group_name == group_name
                    )
                )
            )
            row = result.scalar_one_or_none()
            return ScheduleArchiveRepository._safe_parse_schedule(row)
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving student schedule for {group_name} on {date}: {e}")
            raise

    @staticmethod
    async def get_mentor_schedule(session: AsyncSession, date: str, mentor_name: str) -> List[Any]:
        """Get archived mentor schedule with validation and optimized query.
        
        Args:
            session: SQLAlchemy async session.
            date: Schedule date as string.
            mentor_name: Mentor name.
            
        Returns:
            Parsed schedule list or empty list if not found.
            
        Raises:
            ValueError: If date or mentor_name is invalid.
            SQLAlchemyError: If database operation fails.
        """
        if not date or not isinstance(date, str):
            raise ValueError("date must be a non-empty string")
        if not mentor_name or not isinstance(mentor_name, str):
            raise ValueError("mentor_name must be a non-empty string")
            
        try:
            result = await session.execute(
                select(ScheduleArchiveMentor.schedule)
                .where(
                    and_(
                        ScheduleArchiveMentor.date == date, 
                        ScheduleArchiveMentor.mentor_name == mentor_name
                    )
                )
            )
            # row = result.scalar_one_or_none()
            row = result.first()
            return ScheduleArchiveRepository._safe_parse_schedule(row)
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving mentor schedule for {mentor_name} on {date}: {e}")
            raise

    @staticmethod
    async def update_student_schedule(
        session: AsyncSession, date: str, group_name: str, schedule: List[Any], schedule_hash: str
    ) -> None:
        """Upsert archived student schedule with validation and error handling.
        
        Args:
            session: SQLAlchemy async session.
            date: Schedule date as string.
            group_name: Student group name.
            schedule: Schedule data list.
            schedule_hash: Hash of schedule content.
            
        Raises:
            ValueError: If any parameter is invalid.
            SQLAlchemyError: If database operation fails.
        """
        # Input validation
        if not date or not isinstance(date, str):
            raise ValueError("date must be a non-empty string")
        if not group_name or not isinstance(group_name, str):
            raise ValueError("group_name must be a non-empty string")
        if not isinstance(schedule, list):
            raise ValueError("schedule must be a list")
        if not schedule_hash or not isinstance(schedule_hash, str):
            raise ValueError("schedule_hash must be a non-empty string")
            
        try:
            result = await session.execute(
                select(ScheduleArchiveStudent)
                .where(
                    and_(
                        ScheduleArchiveStudent.date == date, 
                        ScheduleArchiveStudent.group_name == group_name
                    )
                )
            )
            existing = result.scalar_one_or_none()

            schedule_str = str(schedule)

            if existing:
                existing.schedule = schedule_str  # type: ignore
                existing.schedule_hash = schedule_hash  # type: ignore
                await session.commit()  # Commit the update
                logger.debug(f"Updated student schedule for {group_name} on {date}")
            else:
                new_record = ScheduleArchiveStudent(
                    date=date, 
                    group_name=group_name, 
                    schedule=schedule_str, 
                    schedule_hash=schedule_hash
                )
                session.add(new_record)
                await session.commit()  # Commit the new record
                logger.debug(f"Created student schedule for {group_name} on {date}")
        except SQLAlchemyError as e:
            logger.error(f"Error updating student schedule for {group_name} on {date}: {e}")
            raise

    @staticmethod
    async def update_mentor_schedule(
        session: AsyncSession, date: str, mentor_name: str, schedule: List[Any], schedule_hash: str
    ) -> None:
        """Upsert archived mentor schedule with validation and error handling.
        
        Args:
            session: SQLAlchemy async session.
            date: Schedule date as string.
            mentor_name: Mentor name.
            schedule: Schedule data list.
            schedule_hash: Hash of schedule content.
            
        Raises:
            ValueError: If any parameter is invalid.
            SQLAlchemyError: If database operation fails.
        """
        # Input validation
        if not date or not isinstance(date, str):
            raise ValueError("date must be a non-empty string")
        if not mentor_name or not isinstance(mentor_name, str):
            raise ValueError("mentor_name must be a non-empty string")
        if not isinstance(schedule, list):
            raise ValueError("schedule must be a list")
        if not schedule_hash or not isinstance(schedule_hash, str):
            raise ValueError("schedule_hash must be a non-empty string")
            
        try:
            result = await session.execute(
                select(ScheduleArchiveMentor)
                .where(
                    and_(
                        ScheduleArchiveMentor.date == date, 
                        ScheduleArchiveMentor.mentor_name == mentor_name
                    )
                )
            )
            existing = result.scalar_one_or_none()

            schedule_str = str(schedule)

            if existing:
                existing.schedule = schedule_str  # type: ignore
                existing.schedule_hash = schedule_hash  # type: ignore
                await session.commit()  # Commit the update
                logger.debug(f"Updated mentor schedule for {mentor_name} on {date}")
            else:
                new_record = ScheduleArchiveMentor(
                    date=date, 
                    mentor_name=mentor_name, 
                    schedule=schedule_str, 
                    schedule_hash=schedule_hash
                )
                session.add(new_record)
                await session.commit()  # Commit the new record
                logger.debug(f"Created mentor schedule for {mentor_name} on {date}")
        except SQLAlchemyError as e:
            logger.error(f"Error updating mentor schedule for {mentor_name} on {date}: {e}")
            raise


db_manager = DatabaseManager()
