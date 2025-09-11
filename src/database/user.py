import sqlite3
from typing import Dict, List, Optional


class Users:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def build(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_contacted_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """
        )
        conn.commit()
        conn.close()

    """CREATE"""

    def create(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, approved_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (user_id, username, first_name, last_name),
        )

        user_db_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return user_db_id

    """READ"""

    def get_by_id(self, user_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM users WHERE user_id = ? AND is_active = 1
            """,
            (user_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "approved_at": row[5],
                "last_contacted_at": row[6],
                "is_active": bool(row[7]),
            }
        return None

    def get_all_active(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM users WHERE is_active = 1 ORDER BY approved_at DESC
            """
        )

        rows = cursor.fetchall()

        # Also check total users in table
        cursor.execute("SELECT COUNT(*) FROM users")
        total_count = cursor.fetchone()[0]

        # Check active vs inactive
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        active_count = cursor.fetchone()[0]

        conn.close()

        users = []
        for row in rows:
            users.append(
                {
                    "id": row[0],
                    "user_id": row[1],
                    "username": row[2],
                    "first_name": row[3],
                    "last_name": row[4],
                    "approved_at": row[5],
                    "last_contacted_at": row[6],
                    "is_active": bool(row[7]),
                }
            )
        return users

    """UPDATE"""

    def update(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, approved_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (username, first_name, last_name, user_id),
        )

        conn.commit()
        conn.close()

    def upsert(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ) -> int:
        existing_user = self.get_by_id(user_id)

        if existing_user:
            self.update(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            return existing_user["id"]
        else:
            return self.create(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )

    def update_last_contacted(self, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users SET last_contacted_at = CURRENT_TIMESTAMP WHERE user_id = ?
            """,
            (user_id,),
        )

        conn.commit()
        conn.close()

    def deactivate(self, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users SET is_active = 0 WHERE user_id = ?
            """,
            (user_id,),
        )

        conn.commit()
        conn.close()
