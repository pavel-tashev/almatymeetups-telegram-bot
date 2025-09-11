import sqlite3

from config.settings import DATABASE_URL

from .request import Request
from .user import Users


class Model:
    def __init__(self):
        self.db_path = DATABASE_URL.replace("sqlite:///", "")
        self.requests = Request(self.db_path)
        self.users = Users(self.db_path)
        self.init_database()

    def init_database(self):
        self.requests.build()
        self.users.build()
