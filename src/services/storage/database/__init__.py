from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

DATABASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "storage"
DATABASE_PATH = DATABASE_DIR / "flood_control.db"

def get_database_path() -> Path:
    """获取数据库文件路径"""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH

def get_database_uri() -> str:
    """获取数据库URI"""
    return f"sqlite:///{get_database_path()}"
