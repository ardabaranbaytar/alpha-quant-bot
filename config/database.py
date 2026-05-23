# config/database.py

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from .settings import settings

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(
            settings.DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True  
        )
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)

    def get_session(self):
        """Returns a DB session that can be safely called by any module."""
        return self.Session()

    def execute_query(self, query_str: str, params: dict = None):
        """Helper function for executing SQL quickly and safely."""
        with self.engine.connect() as conn:
            result = conn.execute(text(query_str), params or {})
            return result.fetchall()

db = DatabaseManager()