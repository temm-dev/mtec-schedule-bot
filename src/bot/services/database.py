import asyncio
import sqlite3 as sql3
from datetime import datetime

import aiosqlite
from config.bot_config import SECRET_KEY
from cryptography.fernet import Fernet


class DatabaseUsers:
    """A class for working with user data"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.db:
            await self.db.close()

    @classmethod
    async def create(cls, db_path: str) -> "DatabaseUsers":
        self = cls(db_path)
        self.db = await aiosqlite.connect(db_path)
        self.db.row_factory = aiosqlite.Row
        return self

    async def create_table(self) -> None:
        """A method for creating a table"""
        fields_table = """
        id INTEGER PRIMARY KEY,
        user_id INTEGER,

        user_status TEXT,
        mentor_name TEXT DEFAULT None,
        student_group TEXT DEFAULT None,

        user_theme TEXT DEFAULT Classic,

        ejournal_name TEXT DEFAULT None,
        ejournal_password TEXT DEFAULT None,

        toggle_schedule BOOL DEFAULT False,
        all_semesters BOOL DEFAULT False
        """

        async with self.lock:
            async with self.db.execute(f"""CREATE TABLE IF NOT EXISTS Users ({fields_table})"""):
                await self.db.commit()

    async def check_user_in_db(self, user_id: int) -> bool:
        """A method for verifying the presence of a user in the database"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT user_id FROM Users WHERE user_id == ?""",
                (user_id,),
            ) as cursor:
                user_in = await cursor.fetchone()

        return bool(user_in)

    async def get_user_status(self, user_id: int):
        """Method for getting user status [student, mentor]"""
        async with self.lock:
            async with self.db.execute(f"""SELECT user_status FROM Users WHERE user_id == ?""", (user_id,)) as cursor:
                row = await cursor.fetchone()
                status = row[0] if row else ""

        return status

    async def get_users(self) -> list[int]:
        """A method for getting the IDs of all users in the database"""
        async with self.lock:
            async with self.db.execute(f"""SELECT user_id FROM Users""") as cursor:
                data = await cursor.fetchall()
                users_ids = [user_id[0] for user_id in data]

        return users_ids

    async def get_groups(self) -> list[str]:  # TODO - Unused function?
        """Method for getting all the groups in the database"""
        async with self.lock:
            async with self.db.execute(f"""SELECT student_group FROM Users """) as cursor:
                row = await cursor.fetchall()
                groups = set()

                [groups.add(group[0]) for group in row]

        return list(groups)

    async def get_users_by_group(self, group: str) -> list[int]:
        """Method for getting users from a group"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT user_id FROM Users WHERE user_status == ? AND student_group == ? AND toggle_schedule == ? """,
                ("student", group, 0),
            ) as cursor:
                row = await cursor.fetchall()
                users_ids = [user_id[0] for user_id in row]

        return users_ids

    async def get_users_by_theme(self, group: str, theme: str = "Classic") -> list[int]:
        """A method for getting users from a group by theme"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT user_id FROM Users WHERE student_group == ? AND user_theme == ? AND toggle_schedule == ? """,
                (group, theme, 0),
            ) as cursor:
                data = await cursor.fetchall()
                users_ids = [user_id[0] for user_id in data]

        return users_ids

    async def get_user_group(self, user_id: int) -> str:
        """Method for getting the user's group"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT student_group FROM Users WHERE user_id == ?""",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                student_group = row[0] if row else ""

        return student_group

    async def get_user_theme(self, user_id: int) -> str:
        """The method for getting the user's theme"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT user_theme FROM Users WHERE user_id == ?""",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                user_theme = row[0] if row else "Classic"

        return user_theme

    async def get_user_settigs(self, user_id: int) -> dict[str, bool]:
        """Method for getting user settings"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT COALESCE(toggle_schedule, 0), COALESCE(all_semesters, 0) FROM Users WHERE user_id == ? """,
                (user_id,),
            ) as cursor:
                data = await cursor.fetchone()

        if not data:
            return {"toggle_schedule": False, "all_semesters": False}

        toggle_schedule = bool(int(data[0]))
        all_semesters = bool(int(data[1]))

        return {"toggle_schedule": toggle_schedule, "all_semesters": all_semesters}

    async def get_user_ejournal_info(self, user_id: int) -> list[str] | list:
        """A method for obtaining user's personal data for logging into an electronic journal"""
        async with self.lock:
            async with self.db.execute(
                "SELECT ejournal_name, ejournal_password FROM Users WHERE user_id = ? LIMIT 1",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return []

        fio = row["ejournal_name"]
        pwd = row["ejournal_password"]

        if fio == "None" and pwd == "None":
            return []

        decrypted_fio = cipher.decrypt(fio).decode()
        decrypted_pwd = cipher.decrypt(pwd).decode()

        if decrypted_fio == "None" or decrypted_pwd == "None":
            return []

        ejouranl_info = [decrypted_fio, decrypted_pwd]
        return ejouranl_info

    async def get_mentors(self) -> list:
        """Method for getting mentors ids"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT user_id, mentor_name FROM Users WHERE user_status == ? AND toggle_schedule == ? """,
                ("mentor", 0),
            ) as cursor:
                data = await cursor.fetchall()

                mentors = []
                for mentor in data:
                    mentor_id = mentor[0]
                    mentor_name = mentor[1]
                    mentors.append([mentor_id, mentor_name])

        return mentors

    async def get_mentor_name_by_id(self, user_id: int) -> str | None:
        """Method for getting mentors ids"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT mentor_name FROM Users WHERE user_id == ? AND user_status == ? AND toggle_schedule == ? """,
                (user_id, "mentor", 0),
            ) as cursor:
                data = await cursor.fetchone()
                mentor_name = data[0] if data else None

        return mentor_name

    async def change_user_settings(self, setting: str, setting_status: bool, user_id: int) -> None:
        """A method for changing user settings"""
        async with self.lock:
            async with self.db.execute(
                f"""UPDATE Users SET "{setting}" = ? WHERE user_id = ? """,
                (setting_status, user_id),
            ):
                await self.db.commit()

    async def change_user_theme(self, user_id: int, theme: str) -> None:
        """A method for changing the user's theme"""
        async with self.lock:
            async with self.db.execute(
                f"""UPDATE Users SET user_theme = ? WHERE user_id = ? """,
                (theme, user_id),
            ):
                await self.db.commit()

    async def add_user_ejournal_info(self, user_id: int, info: list) -> None:
        """A method for adding personal data to the user's electronic journal"""
        fio, pwd = info[0], info[1]

        encrypted_fio = cipher.encrypt(fio.encode())
        encrypted_password = cipher.encrypt(pwd.encode())

        async with self.lock:
            async with self.db.execute(
                f"""UPDATE Users SET ejournal_name = ?, ejournal_password = ? WHERE user_id = ? """,
                (encrypted_fio, encrypted_password, user_id),
            ):
                await self.db.commit()

    async def add_user(
        self,
        user_id: int,
        user_status: str,
        mentor_name: str = "None",
        student_group: str = "None",
    ) -> None:
        """Method for adding a user to the database"""
        async with self.lock:
            async with self.db.execute(
                f"""INSERT INTO Users (user_id, user_status, mentor_name, student_group) VALUES(?, ?, ?, ?)""",
                (user_id, user_status, mentor_name, student_group),
            ):
                await self.db.commit()

            print(f"👤 Пользователь | {user_id} - {student_group} | добавлен 🆕")

    async def update_student(self, user_id: int, user_group: str):
        """Method for changing the student's info"""
        async with self.lock:
            async with self.db.execute(
                """UPDATE Users SET user_status = ?, student_group = ?, mentor_name = ? WHERE user_id = ? """,
                ("student", user_group, "None", user_id),
            ):
                await self.db.commit()

        # print(f"👤 Пользователь перезаписан 🔄 | {user_id} - {user_group} | ℹ️")

    async def update_mentor(self, user_id: int, mentor_name: str):
        """Method for changing the mentor's info"""
        async with self.lock:
            async with self.db.execute(
                """UPDATE Users SET user_status = ?, student_group = ?, mentor_name = ? WHERE user_id = ? """,
                ("mentor", "None", mentor_name, user_id),
            ):
                await self.db.commit()

        # print(f"👤 Пользователь перезаписан 🔄 | {user_id} - {mentor_name} | ℹ️")

    async def delete_user_ejournal_info(self, user_id: int) -> None:
        """A method for deleting a user's personal data to log in to an electronic journal"""
        async with self.lock:
            async with self.db.execute(
                f"""UPDATE Users SET ejournal_name = ?, ejournal_password = ? WHERE user_id = ? """,
                (
                    "None",
                    "None",
                    user_id,
                ),
            ):
                await self.db.commit()

    async def delete_user(self, user_id: int) -> None:
        """A method for deleting a user from the database"""
        async with self.lock:
            async with self.db.execute(f"""DELETE FROM Users WHERE user_id == ? """, (user_id,)):
                await self.db.commit()


class DatabaseHashes:
    """A class for working with schedule hashes"""

    def __init__(self, name_db: str) -> None:
        """Initializing necessary dependencies"""
        self.conn = sql3.connect(name_db, check_same_thread=False)
        self.cur = self.conn.cursor()

    def create_table(self, name_table: str) -> None:
        """A method for creating a table"""
        self.cur.execute(
            f"""
        CREATE TABLE IF NOT EXISTS "{name_table}" (
            id INTEGER PRIMARY KEY,
            group_name TEXT NOT NULL,
            date DATE NOT NULL,
            hash_value TEXT NOT NULL
        )
        """
        )
        self.conn.commit()

    def add_hash(self, group_name: str, date: str, hash_value: str) -> bool:
        """A method for adding a schedule hash to the database"""
        self.cur.execute(
            "SELECT hash_value FROM schedule_hashes WHERE group_name = ? AND date = ?",
            (group_name, date),
        )
        result = self.cur.fetchone()

        if result is None:
            self.cur.execute(
                """
                INSERT INTO schedule_hashes (group_name, date, hash_value)
                VALUES (?, ?, ?)
                """,
                (group_name, date, hash_value),
            )
            self.conn.commit()
            return True

        return False

    def change_hash(self, group_name: str, date: str, hash_value: str) -> None:
        """A method for changing the hash"""
        self.cur.execute(
            """
            UPDATE schedule_hashes
            SET hash_value = ?
            WHERE group_name = ? AND date = ?
            """,
            (hash_value, group_name, date),
        )
        self.conn.commit()

    def check_hash_change(self, group_name: str, date: str, hash_value: str) -> bool | None:
        """A method for checking the location of the schedule hash in the database"""
        self.cur.execute(
            "SELECT hash_value FROM schedule_hashes WHERE group_name = ? AND date = ?",
            (group_name, date),
        )
        result = self.cur.fetchone()

        if result is None:
            self.add_hash(group_name, date, hash_value)
            return False

        if result[0] != hash_value:
            return True

        return False

    def cleanup_old_hashes(self) -> None:
        """A method for deleting old schedule hashes"""
        now = datetime.now()
        year = now.day
        month = now.month
        day = now.year
        date = f"{day}.{month}.{year}"

        self.cur.execute("DELETE FROM schedule_hashes WHERE date < ?", (date,))
        self.conn.commit()
        print("#️⃣  Старые записи хешей удалены. 🗑️")


class DatabaseScheduleArchive:
    """A class for working with schedule data"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.db:
            await self.db.close()

    @classmethod
    async def create(cls, db_path: str) -> "DatabaseScheduleArchive":
        self = cls(db_path)
        self.db = await aiosqlite.connect(db_path)
        self.db.row_factory = aiosqlite.Row
        return self

    async def create_table(self) -> None:
        """A method for creating a table"""
        fields_table = """
        id INTEGER PRIMARY KEY,
        date INTEGER,
        group_name TEXT,
        schedule TEXT,
        schedule_hash TEXT
        """

        async with self.lock:
            async with self.db.execute(f"""CREATE TABLE IF NOT EXISTS schedule_archive ({fields_table})"""):
                await self.db.commit()

    async def add_schedule(self, date: str, group_name: str, schedule: list, schedule_hash: str) -> None:
        """A method for add schedule in table"""
        async with self.lock:
            async with self.db.execute(
                f"""INSERT INTO schedule_archive (date, group_name, schedule, schedule_hash) VALUES(?, ?, ?, ?)""",
                (date, group_name, str(schedule), schedule_hash),
            ):
                await self.db.commit()

    async def get_schedule(self, date: str, group_name: str):
        """A method for add schedule in table"""
        async with self.lock:
            async with self.db.execute(
                f"""SELECT date, group_name, schedule, schedule_hash FROM schedule_archive WHERE date = ? AND group_name = ?""",
                (date, group_name),
            ) as cursor:
                row = await cursor.fetchall()
                data = []

                for i in row:
                    temp = []
                    for j in i:
                        temp.append(j)

                    data.append(temp)

        return data


cipher = Fernet(SECRET_KEY)
