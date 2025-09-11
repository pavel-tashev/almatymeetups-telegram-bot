import sqlite3
from typing import Dict, Optional


class Request:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def build(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                admin_message_id INTEGER,
                user_explanation TEXT,
                UNIQUE(user_id)
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
            INSERT OR REPLACE INTO requests (user_id, username, first_name, last_name, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            """,
            (user_id, username, first_name, last_name),
        )

        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return request_id

    """READ"""

    def get_by_user_id(self, user_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM requests WHERE user_id = ?
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
                "status": row[5],
                "created_at": row[6],
                "approved_at": row[7],
                "admin_message_id": row[8],
                "user_explanation": row[9] if len(row) > 9 else None,
            }
        return None

    def get_by_id(self, request_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM requests WHERE id = ?
            """,
            (request_id,),
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
                "status": row[5],
                "created_at": row[6],
                "approved_at": row[7],
                "admin_message_id": row[8],
                "user_explanation": row[9] if len(row) > 9 else None,
            }
        return None

    """UPDATE"""

    def update_user_explanation(self, request_id: int, explanation: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE requests SET user_explanation = ? WHERE id = ?
            """,
            (explanation, request_id),
        )

        conn.commit()
        conn.close()

    def update_status(self, request_id: int, status: str, admin_message_id: int = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status == "approved":
            cursor.execute(
                """
                UPDATE requests 
                SET status = ?, approved_at = CURRENT_TIMESTAMP, admin_message_id = ?
                WHERE id = ?
                """,
                (status, admin_message_id, request_id),
            )
        else:
            cursor.execute(
                """
                UPDATE requests 
                SET status = ?, admin_message_id = ?
                WHERE id = ?
                """,
                (status, admin_message_id, request_id),
            )

        conn.commit()
        conn.close()
