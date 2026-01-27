from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """Модель пользователя"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    user_status = Column(String(20), nullable=False)  # student, mentor
    mentor_name = Column(String(100), default=None)
    student_group = Column(String(50), default=None)
    user_theme = Column(String(50), default="Classic")
    ejournal_name = Column(Text, default=None)
    ejournal_password = Column(Text, default=None)
    toggle_schedule = Column(Boolean, default=False)
    all_semesters = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class Chat(Base):
    """Модель для чатов/групп Telegram"""

    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    chat_type = Column(String(20))  # 'group', 'supergroup', 'channel'

    subscribed_to_group = Column(String(50), nullable=True)
    subscribed_to_mentor = Column(String(100), nullable=True)

    send_daily = Column(Boolean, default=True)
    send_changes = Column(Boolean, default=True)
    theme = Column(String(50), default="Classic")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ScheduleHash(Base):
    """Модель для хранения хэшей расписаний"""

    __tablename__ = "schedule_hashes"

    id = Column(Integer, primary_key=True)
    group_name = Column(String(50), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    hash_value = Column(String(64), nullable=False)

    __table_args__ = ({"extend_existing": True},)


class ScheduleArchiveStudent(Base):
    """Архив расписаний для студентов"""

    __tablename__ = "schedule_archive_students"

    id = Column(Integer, primary_key=True)
    date = Column(Text, nullable=False, index=True)
    group_name = Column(String(50), nullable=False, index=True)
    schedule = Column(Text, nullable=False)
    schedule_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ScheduleArchiveMentor(Base):
    """Архив расписаний для преподавателей"""

    __tablename__ = "schedule_archive_mentors"

    id = Column(Integer, primary_key=True)
    date = Column(Text, nullable=False, index=True)
    mentor_name = Column(String(100), nullable=False, index=True)
    schedule = Column(Text, nullable=False)
    schedule_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
