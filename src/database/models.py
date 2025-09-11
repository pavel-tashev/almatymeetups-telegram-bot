import sqlite3
from datetime import datetime
from typing import Dict, Optional

from config.settings import DATABASE_URL


class Database:
    def __init__(self):
        self.db_path = DATABASE_URL.replace("sqlite:///", "")
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create requests table
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

        # Create users table for approved users
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

    def create_request(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ) -> int:
        """Create a new join request"""
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

    def update_user_explanation(self, request_id: int, explanation: str):
        """Update the user's explanation for a request"""
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

    def get_request(self, user_id: int) -> Optional[Dict]:
        """Get a request by user_id"""
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

    def update_request_status(
        self, request_id: int, status: str, admin_message_id: int = None
    ):
        """Update request status"""
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

    def get_request_by_id(self, request_id: int) -> Optional[Dict]:
        """Get a request by its ID"""
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

    def add_approved_user(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ) -> int:
        """Add a user to the approved users table"""
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

    def get_all_active_users(self) -> list[Dict]:
        """Get all active approved users"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM users WHERE is_active = 1 ORDER BY approved_at DESC
        """
        )

        rows = cursor.fetchall()
        conn.close()

        users = []
        for row in rows:
            users.append({
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "approved_at": row[5],
                "last_contacted_at": row[6],
                "is_active": bool(row[7]),
            })
        return users

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get a user by their Telegram user_id"""
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

    def update_last_contacted(self, user_id: int):
        """Update the last contacted timestamp for a user"""
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

    def deactivate_user(self, user_id: int):
        """Deactivate a user (soft delete)"""
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