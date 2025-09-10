import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import DATABASE_URL


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
                UNIQUE(user_id)
            )
        """
        )

        # Create responses table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                question_id TEXT NOT NULL,
                answer TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES requests (id)
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

    def add_response(self, request_id: int, question_id: str, answer: str):
        """Add a response to a request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO responses (request_id, question_id, answer)
            VALUES (?, ?, ?)
        """,
            (request_id, question_id, answer),
        )

        conn.commit()
        conn.close()

    def get_responses(self, request_id: int) -> List[Dict]:
        """Get all responses for a request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT question_id, answer FROM responses WHERE request_id = ?
        """,
            (request_id,),
        )

        responses = [
            {"question_id": row[0], "answer": row[1]} for row in cursor.fetchall()
        ]
        conn.close()

        return responses

    def get_expired_requests(self) -> List[Dict]:
        """Get requests that have expired (older than timeout period)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate the cutoff time
        cutoff_time = datetime.now() - timedelta(hours=24)

        cursor.execute(
            """
            SELECT * FROM requests 
            WHERE status = 'pending' AND created_at < ?
        """,
            (cutoff_time,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "first_name": row[3],
                "last_name": row[4],
                "status": row[5],
                "created_at": row[6],
                "approved_at": row[7],
                "admin_message_id": row[8],
            }
            for row in rows
        ]

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
            }
        return None
