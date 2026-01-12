import sqlite3
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from config import DB_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = None):
        # Автоматическое определение пути для облака
        if db_path is None:
            if 'RENDER' in os.environ or 'RAILWAY' in os.environ:
                # Для облачных платформ используем /tmp/
                self.db_path = "/tmp/database.db"
                logger.info(f"Используем базу данных в /tmp/database.db")
            else:
                self.db_path = "database.db"
        else:
            self.db_path = db_path
        
        logger.info(f"База данных: {self.db_path}")
        self.init_database()
        
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS employees (
                        user_id INTEGER PRIMARY KEY,
                        full_name TEXT NOT NULL,
                        shift_number TEXT NOT NULL CHECK(shift_number IN ('1', '2', '3', '4')),
                        vacation_rate INTEGER DEFAULT 0,
                        sick_rate INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        date DATE NOT NULL,
                        day_type TEXT NOT NULL CHECK(day_type IN ('work', 'reinforce', 'vacation', 'sick', 'unpaid')),
                        hours REAL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, date),
                        FOREIGN KEY (user_id) REFERENCES employees (user_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS absence_periods (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        period_type TEXT NOT NULL CHECK(period_type IN ('vacation', 'sick')),
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CHECK(end_date >= start_date),
                        FOREIGN KEY (user_id) REFERENCES employees (user_id) ON DELETE CASCADE
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_settings (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        monthly_salary INTEGER DEFAULT 137500,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_user_date ON records(user_id, date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_date ON records(date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_periods_user ON absence_periods(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_periods_dates ON absence_periods(start_date, end_date)")
                
                cursor.execute("INSERT OR IGNORE INTO system_settings (id, monthly_salary) VALUES (1, 137500)")
                
                conn.commit()
                logger.info("База данных инициализирована")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def add_employee(self, user_id: int, full_name: str, shift_number: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO employees (user_id, full_name, shift_number) VALUES (?, ?, ?)",
                    (user_id, full_name, shift_number)
                )
                conn.commit()
                logger.info(f"Добавлен сотрудник: {full_name} (ID: {user_id})")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"Сотрудник {user_id} уже существует")
            return False
        except Exception as e:
            logger.error(f"Ошибка добавления сотрудника: {e}")
            return False
    
    def get_employee(self, user_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, full_name, shift_number, vacation_rate, sick_rate FROM employees WHERE user_id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения сотрудника: {e}")
            return None
    
    def get_all_employees(self) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, full_name, shift_number, vacation_rate, sick_rate FROM employees ORDER BY full_name"
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения списка сотрудников: {e}")
            return []
    
    def update_employee_rates(self, user_id: int, vacation_rate: int = None, sick_rate: int = None) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []
                
                if vacation_rate is not None:
                    updates.append("vacation_rate = ?")
                    params.append(vacation_rate)
                
                if sick_rate is not None:
                    updates.append("sick_rate = ?")
                    params.append(sick_rate)
                
                if not updates:
                    return False
                
                params.append(user_id)
                query = f"UPDATE employees SET {', '.join(updates)} WHERE user_id = ?"
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления ставок: {e}")
            return False
    
    def add_record(self, user_id: int, date: date, day_type: str, hours: float = 0) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO records (user_id, date, day_type, hours)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, date.isoformat(), day_type, hours)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления записи: {e}")
            return False
    
    def get_record(self, user_id: int, date: date) -> Optional[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, user_id, date, day_type, hours FROM records WHERE user_id = ? AND date = ?",
                    (user_id, date.isoformat())
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения записи: {e}")
            return None
    
    def get_records_for_month(self, user_id: int, year: int, month: int) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                start_date = f"{year:04d}-{month:02d}-01"
                end_date = f"{year:04d}-{month+1:02d}-01" if month < 12 else f"{year+1:04d}-01-01"
                
                cursor.execute(
                    """
                    SELECT id, user_id, date, day_type, hours 
                    FROM records 
                    WHERE user_id = ? AND date >= ? AND date < ?
                    ORDER BY date
                    """,
                    (user_id, start_date, end_date)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения записей за месяц: {e}")
            return []
    
    def get_last_records(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, date, day_type, hours 
                    FROM records 
                    WHERE user_id = ? 
                    ORDER BY date DESC, id DESC 
                    LIMIT ?
                    """,
                    (user_id, limit)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения последних записей: {e}")
            return []
    
    def delete_record(self, record_id: int) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления записи: {e}")
            return False
    
    def add_absence_period(self, user_id: int, period_type: str, start_date: date, end_date: date) -> int:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO absence_periods (user_id, period_type, start_date, end_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, period_type, start_date.isoformat(), end_date.isoformat())
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления периода: {e}")
            return -1
    
    def get_absence_periods(self, user_id: int, period_type: str = None) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if period_type:
                    cursor.execute(
                        """
                        SELECT id, period_type, start_date, end_date, 
                               julianday(end_date) - julianday(start_date) + 1 as days
                        FROM absence_periods 
                        WHERE user_id = ? AND period_type = ?
                        ORDER BY start_date DESC
                        """,
                        (user_id, period_type)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id, period_type, start_date, end_date,
                               julianday(end_date) - julianday(start_date) + 1 as days
                        FROM absence_periods 
                        WHERE user_id = ?
                        ORDER BY start_date DESC
                        """,
                        (user_id,)
                    )
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения периодов: {e}")
            return []
    
    def delete_absence_period(self, period_id: int) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM absence_periods WHERE id = ?", (period_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления периода: {e}")
            return False
    
    def get_monthly_salary(self) -> int:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT monthly_salary FROM system_settings WHERE id = 1")
                row = cursor.fetchone()
                return row['monthly_salary'] if row else 137500
        except Exception as e:
            logger.error(f"Ошибка получения оклада: {e}")
            return 137500
    
    def update_monthly_salary(self, salary: int) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE system_settings 
                    SET monthly_salary = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                    """,
                    (salary,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка обновления оклада: {e}")
            return False
    
    def check_date_conflict(self, user_id: int, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT date, day_type, hours 
                    FROM records 
                    WHERE user_id = ? AND date >= ? AND date <= ?
                    ORDER BY date
                    """,
                    (user_id, start_date.isoformat(), end_date.isoformat())
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка проверки конфликтов: {e}")
            return []

# Глобальный экземпляр базы данных
db = Database()
