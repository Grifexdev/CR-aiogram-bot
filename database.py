import sqlite3
import logging
from typing import Optional, List, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    royale_nickname TEXT,
                    royale_tag TEXT,
                    role TEXT DEFAULT 'member',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица админов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    telegram_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица истории атак в КВ
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS war_attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    war_date DATE,
                    attacks_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
                )
            """)
            
            conn.commit()
            logger.info("База данных инициализирована")
    
    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def add_user(self, telegram_id: int, username: Optional[str] = None):
        """Добавить пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO users (telegram_id, username)
                VALUES (?, ?)
            """, (telegram_id, username))
            conn.commit()
    
    def update_user_royale_info(self, telegram_id: int, royale_nickname: str, royale_tag: str):
        """Обновить информацию о нике и теге в рояле"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET royale_nickname = ?, royale_tag = ?, last_activity = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (royale_nickname, royale_tag, telegram_id))
            conn.commit()
    
    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получить информацию о пользователе"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_user_by_royale_tag(self, royale_tag: str) -> Optional[Dict]:
        """Найти пользователя по тегу в Clash Royale"""
        clean_tag = royale_tag.replace("#", "").upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE UPPER(REPLACE(royale_tag, '#', '')) = ?", (clean_tag,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY joined_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_users_with_royale_info(self) -> List[Dict]:
        """Получить пользователей с указанным ником в рояле"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users 
                WHERE royale_nickname IS NOT NULL AND royale_tag IS NOT NULL
                ORDER BY royale_nickname
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def set_user_role(self, telegram_id: int, role: str):
        """Установить роль пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET role = ? WHERE telegram_id = ?
            """, (role, telegram_id))
            conn.commit()
    
    def add_admin(self, telegram_id: int, added_by: int):
        """Добавить админа"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO admins (telegram_id, added_by)
                VALUES (?, ?)
            """, (telegram_id, added_by))
            conn.commit()
    
    def remove_admin(self, telegram_id: int):
        """Удалить админа"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
    
    def is_admin(self, telegram_id: int) -> bool:
        """Проверить, является ли пользователь админом"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,))
            return cursor.fetchone() is not None
    
    def get_all_admins(self) -> List[int]:
        """Получить список всех админов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM admins")
            return [row[0] for row in cursor.fetchall()]
    
    def update_war_attacks(self, telegram_id: int, war_date: str, attacks_count: int):
        """Обновить количество атак в КВ"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO war_attacks (telegram_id, war_date, attacks_count, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (telegram_id, war_date, attacks_count))
            conn.commit()
    
    def get_users_without_attacks(self, war_date: str) -> List[Dict]:
        """Получить пользователей, которые не атаковали в КВ"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.* FROM users u
                LEFT JOIN war_attacks wa ON u.telegram_id = wa.telegram_id AND wa.war_date = ?
                WHERE (wa.attacks_count IS NULL OR wa.attacks_count = 0)
                AND u.royale_tag IS NOT NULL
            """, (war_date,))
            return [dict(row) for row in cursor.fetchall()]


# Глобальный экземпляр базы данных
db = Database()

