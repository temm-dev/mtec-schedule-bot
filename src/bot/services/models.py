"""SQLAlchemy database models for MTEC schedule bot.

This module defines the database schema using SQLAlchemy ORM declarative
base. Contains models for users, chats, schedule archives, and hash tracking.

Models:
    User: Bot user information and preferences
    Chat: Telegram chat/group information and subscriptions
    ScheduleHash: Hash values for detecting schedule changes
    ScheduleArchiveStudent: Archived student schedules
    ScheduleArchiveMentor: Archived mentor schedules
"""

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """User model for storing bot user information and preferences.

    Attributes:
        id: Primary key.
        user_id: Telegram user ID (unique).
        user_status: User type ('student' or 'mentor').
        mentor_name: Mentor name (for mentor users).
        student_group: Student group name (for student users).
        user_theme: UI theme preference.
        ejournal_name: Encrypted e-journal username.
        ejournal_password: Encrypted e-journal password.
        toggle_schedule: Whether schedule notifications are enabled.
        all_semesters: Whether to show all semesters.
        created_at: Account creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_status = Column(String(20), nullable=False, index=True)  # student, mentor
    mentor_name = Column(String(100), default=None, index=True)
    student_group = Column(String(50), default=None, index=True)
    user_theme = Column(String(50), default="Classic", index=True)
    ejournal_name = Column(Text, default=None)
    ejournal_password = Column(Text, default=None)
    toggle_schedule = Column(Boolean, default=False, index=True)
    all_semesters = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Chat(Base):
    """Telegram chat/group model for subscription management.

    Attributes:
        id: Primary key.
        chat_id: Telegram chat ID (unique).
        chat_type: Chat type ('group', 'supergroup', 'channel').
        subscribed_to_group: Subscribed student group name.
        subscribed_to_mentor: Subscribed mentor name.
        send_daily: Whether to send daily schedule notifications.
        send_changes: Whether to send schedule change notifications.
        theme: Chat theme preference.
        created_at: Chat creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    chat_type = Column(String(20), index=True)  # 'group', 'supergroup', 'channel'

    subscribed_to_group = Column(String(50), nullable=True, index=True)
    subscribed_to_mentor = Column(String(100), nullable=True, index=True)

    send_daily = Column(Boolean, default=True, index=True)
    send_changes = Column(Boolean, default=True, index=True)
    theme = Column(String(50), default="Classic", index=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ScheduleHash(Base):
    """Model for storing schedule hash values to detect changes.

    Attributes:
        id: Primary key.
        group_name: Group or mentor identifier.
        date: Schedule date.
        hash_value: SHA-256 hash of schedule content.
    """

    __tablename__ = "schedule_hashes"

    id = Column(Integer, primary_key=True)
    group_name = Column(String(50), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # Store as string 'DD.MM.YYYY'
    hash_value = Column(String(64), nullable=False, index=True)

    __table_args__ = ({"extend_existing": True},)


class ScheduleArchiveStudent(Base):
    """Archive model for student schedules.

    Attributes:
        id: Primary key.
        date: Schedule date as string.
        group_name: Student group name.
        schedule: Serialized schedule data.
        schedule_hash: Hash of schedule content.
        created_at: Archive creation timestamp.
    """

    __tablename__ = "schedule_archive_students"

    id = Column(Integer, primary_key=True)
    date = Column(Text, nullable=False, index=True)
    group_name = Column(String(50), nullable=False, index=True)
    schedule = Column(Text, nullable=False)
    schedule_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())


class ScheduleArchiveMentor(Base):
    """Archive model for mentor schedules.

    Attributes:
        id: Primary key.
        date: Schedule date as string.
        mentor_name: Mentor name.
        schedule: Serialized schedule data.
        schedule_hash: Hash of schedule content.
        created_at: Archive creation timestamp.
    """

    __tablename__ = "schedule_archive_mentors"

    id = Column(Integer, primary_key=True)
    date = Column(Text, nullable=False, index=True)
    mentor_name = Column(String(100), nullable=False, index=True)
    schedule = Column(Text, nullable=False)
    schedule_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
