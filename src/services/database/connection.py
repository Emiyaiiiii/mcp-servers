import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseConnection:
    """数据库连接管理器（单例模式）"""
    
    _instance: Optional['DatabaseConnection'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        from . import get_database_path
        self.db_path = get_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._initialized = True
        logger.info(f"数据库路径: {self.db_path}")
    
    def get_connection(self) -> sqlite3.Connection:
        """获取线程安全的数据库连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA foreign_keys = ON")
            self._local.connection.execute("PRAGMA journal_mode = WAL")
            self._local.connection.execute("PRAGMA synchronous = NORMAL")
        
        return self._local.connection
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"事务回滚: {e}")
            raise
    
    def close(self):
        """关闭连接"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    def execute_query(self, sql: str, params: tuple = None) -> list:
        """执行查询"""
        conn = self.get_connection()
        cursor = conn.execute(sql, params or ())
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def execute_one(self, sql: str, params: tuple = None) -> Optional[dict]:
        """执行查询，返回单条"""
        conn = self.get_connection()
        cursor = conn.execute(sql, params or ())
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def execute_insert(self, sql: str, params: tuple = None) -> int:
        """执行插入，返回最后插入ID"""
        conn = self.get_connection()
        cursor = conn.execute(sql, params or ())
        conn.commit()
        return cursor.lastrowid
    
    def execute_update(self, sql: str, params: tuple = None) -> int:
        """执行更新，返回影响行数"""
        conn = self.get_connection()
        cursor = conn.execute(sql, params or ())
        conn.commit()
        return cursor.rowcount
    
    def execute_script(self, sql_script: str):
        """执行多条SQL语句"""
        conn = self.get_connection()
        conn.executescript(sql_script)
        conn.commit()


db_connection = DatabaseConnection()


def get_db() -> DatabaseConnection:
    """获取数据库连接实例"""
    return db_connection
