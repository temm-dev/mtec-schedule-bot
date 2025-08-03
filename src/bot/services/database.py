import sqlite3 as sql3
from datetime import datetime

from config.bot_config import SECRET_KEY
from cryptography.fernet import Fernet


class DatabaseUsers:
    def __init__(self, name_db: str) -> None:
        """Initializing necessary dependencies"""
        self.conn = sql3.connect(name_db, check_same_thread=False)
        self.cur = self.conn.cursor()

    def create_table(self) -> None:
        """A method for creating a table"""
        fields_text = """
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        user_group TEXT,
        user_theme TEXT DEFAULT Classic,
        ejournal_name TEXT DEFAULT None,
        ejournal_password TEXT DEFAULT None,
        toggle_schedule BOOL DEFAULT False,
        all_semesters BOOL DEFAULT False
        """
        self.cur.execute(f"""CREATE TABLE IF NOT EXISTS Users ({fields_text})""")
        self.conn.commit()

    def check_user_in_db(self, user_id: int, user_group: str) -> bool:
        """A method for verifying the presence of a user in the database"""
        user_in = self.cur.execute(
            f"""SELECT user_id FROM Users WHERE user_id == ? AND user_group == ? """,
            (user_id, user_group),
        )
        if any(user_in.fetchone()):
            return True

        return False

    def get_users(self) -> list[int]:
        """A method for getting the IDs of all users in the database"""
        data = self.cur.execute(f"""SELECT user_id FROM Users """)
        data = data.fetchall()
        users_ids = [ user_id[0] for user_id in data ]

        return users_ids

    def get_groups(self) -> list[str]:
        """Method for getting all the groups in the database"""
        data = self.cur.execute(f"""SELECT user_group FROM Users """)
        data = data.fetchall()
        groups = ( group[0] for group in data )

        return list(groups)

    def get_users_by_group(self, group: str) -> list[int]:
        """Method for getting users from a group"""
        data = self.cur.execute(
            f"""SELECT user_id FROM Users WHERE user_group == ? AND toggle_schedule == 0 """,
            (group,),
        )
        users_ids = [ user_id[0] for user_id in data ]

        return users_ids

    def get_users_by_theme(self, group: str, theme: str = "Classic") -> list[int]:
        """A method for getting users from a group by topic"""
        data = self.cur.execute(
            f"""SELECT user_id FROM Users WHERE user_group == ? AND user_theme == ? """,
            (group, theme),
        )
        data = data.fetchall()
        users_ids = [ user_id[0] for user_id in data ]

        return users_ids

    def get_user_settigs(self, user_id: int) -> dict[str, bool]:
        """Method for getting user settings"""
        toggle_schedule = self.cur.execute(
            f"""SELECT toggle_schedule FROM Users WHERE user_id == ? """,
            (user_id,),
        )
        toggle_schedule = toggle_schedule.fetchone()[0]

        all_semesters = self.cur.execute(
            f"""SELECT all_semesters FROM Users WHERE user_id == ? """,
            (user_id,),
        )
        all_semesters = all_semesters.fetchone()[0]

        settings_dict = {
            "toggle_schedule": bool(toggle_schedule),
            "all_semesters": bool(all_semesters),
        }

        return settings_dict

    def change_user_settings(
        self, setting: str, setting_status: bool, user_id: int
    ) -> None:
        """A method for changing user settings"""
        self.cur.execute(
            f"""UPDATE Users SET "{setting}" = ? WHERE user_id = ? """,
            (setting_status, user_id),
        )
        self.conn.commit()

    def get_group_by_user_id(self, user_id: int) -> str:
        """Method for getting the user's group"""
        data = self.cur.execute(
            f"""SELECT user_group FROM Users WHERE user_id == ? """, (user_id,)
        )
        user_group = data.fetchone()[0]
        return user_group

    def get_theme_by_user_id(self, user_id: int) -> str:
        """The method for getting the user's theme"""
        data = self.cur.execute(
            f"""SELECT user_theme FROM Users WHERE user_id == ? """, (user_id,)
        )
        theme = data.fetchone()[0]
        return theme

    def get_user_ejournal_info(self, user_id: int) -> list[str] | list:
        """A method for obtaining user's personal data for logging into an electronic journal"""
        data = self.cur.execute(
            f"""SELECT ejournal_name, ejournal_password FROM Users WHERE user_id == ? """,
            (user_id,),
        )
        info = data.fetchone()
        fio = info[0]
        password = info[1]

        if fio == "None" or password == "None":
            return []

        decrypted_fio = cipher.decrypt(fio).decode()
        decrypted_password = cipher.decrypt(password).decode()

        if decrypted_fio == "None" or decrypted_password == "None":
            return []

        ejouranl_info = [decrypted_fio, decrypted_password]
        return ejouranl_info

    def add_user_ejournal_info(self, user_id: int, info: list) -> None:
        """A method for adding personal data to the user's electronic journal"""
        fio = info[0]
        password = info[1]

        encrypted_fio = cipher.encrypt(fio.encode())
        encrypted_password = cipher.encrypt(password.encode())

        self.cur.execute(
            f"""UPDATE Users SET ejournal_name = ? WHERE user_id = ? """,
            (encrypted_fio, user_id),
        )
        self.cur.execute(
            f"""UPDATE Users SET ejournal_password = ? WHERE user_id = ? """,
            (encrypted_password, user_id),
        )
        self.conn.commit()

    def delete_user_ejournal_info(self, user_id: int) -> None:
        """A method for deleting a user's personal data to log in to an electronic journal"""
        self.cur.execute(
            f"""UPDATE Users SET ejournal_name = "None" WHERE user_id = ? """,
            (user_id,),
        )
        self.cur.execute(
            f"""UPDATE Users SET ejournal_password = "None" WHERE user_id = ? """,
            (user_id,),
        )
        self.conn.commit()

    def change_user_theme(self, user_id: int, theme: str) -> None:
        """A method for changing the user's theme"""
        self.cur.execute(
            f"""UPDATE Users SET user_theme = ? WHERE user_id = ? """,
            (theme, user_id),
        )
        self.conn.commit()

    def add_user_into_db(
        self,
        user_id: int,
        user_group: str,
        user_theme: str = "Classic",
        ejournal_name: str = "None",
        ejournal_password: str = "None",
    ) -> None:
        """Method for adding a user to the database"""
        user_in = self.cur.execute(
            f"""SELECT user_id FROM Users WHERE user_id == ? """,
            (user_id,),
        )
        if not any(user_in.fetchall()):
            self.cur.execute(
                f"""INSERT INTO Users (user_id, user_group, user_theme, ejournal_name, ejournal_password) VALUES(?, ?, ?, ?, ?)""",
                (user_id, user_group, user_theme, ejournal_name, ejournal_password),
            )
            self.conn.commit()
            print(f"Пользователь | {user_id} - {user_group} | добавлен")
        else:
            print(f"Пользователь | {user_id} - {user_group} | существует")

    def delete_user_from_db(self, user_id: int) -> None:
        """A method for deleting a user from the database"""
        self.cur.execute(f"""DELETE FROM Users WHERE user_id == ? """, (user_id,))
        self.conn.commit()


class DatabaseHashes:
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

    def check_hash_change(
        self, group_name: str, date: str, hash_value: str
    ) -> bool | None:
        """A method for checking the location of the schedule hash in the database"""
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
            return None

        elif result[0] != hash_value:
            self.cur.execute(
                """
            UPDATE schedule_hashes
            SET hash_value = ?
            WHERE group_name = ? AND date = ?
            """,
                (hash_value, group_name, date),
            )

            self.conn.commit()
            return True

        else:
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


cipher = Fernet(SECRET_KEY)
