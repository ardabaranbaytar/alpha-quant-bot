# config/database.py

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from .settings import settings

class DatabaseManager:
    def __init__(self):
        # pool_size: Aynı anda açık kalabilecek maksimum bağlantı sayısı
        # max_overflow: Yoğun anlarda havuzun üzerine çıkabileceği ek bağlantı limiti
        self.engine = create_engine(
            settings.DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True  # Bağlantı kopmalarını otonom test eden kurumsal kalkan
        )
        # Thread-safe (güvenli) oturum yönetimi
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)

    def get_session(self):
        """Her modülün güvenli şekilde çağırabileceği bir DB oturumu döner."""
        return self.Session()

    def execute_query(self, query_str: str, params: dict = None):
        """Hızlı ve güvenli SQL çalıştırmak için yardımcı fonksiyon."""
        with self.engine.connect() as conn:
            result = conn.execute(text(query_str), params or {})
            return result.fetchall()

db = DatabaseManager()