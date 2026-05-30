import sqlite3
from pathlib import Path
from src.services.database import get_database_path
from src.utils.logger import get_logger

logger = get_logger(__name__)


def init_database(force: bool = False):
    """初始化数据库
    
    Args:
        force: 是否强制重建数据库
    """
    db_path = get_database_path()
    sql_dir = Path(__file__).parent.parent.parent.parent / "sql"
    
    logger.info(f"初始化数据库: {db_path}")
    
    if db_path.exists() and not force:
        logger.info("数据库已存在，跳过初始化")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    sql_files = [
        "01_create_tables.sql",
        "02_seed_reservoirs.sql",
        "03_seed_water_levels.sql",
        "04_seed_simulation_params.sql",
        "05_seed_flood_plan.sql",
        "06_seed_dispatch_schemes.sql"
    ]
    
    for sql_file in sql_files:
        sql_path = sql_dir / sql_file
        if sql_path.exists():
            logger.info(f"执行SQL脚本: {sql_file}")
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
                try:
                    cursor.executescript(sql_content)
                    conn.commit()
                    logger.info(f"✓ {sql_file} 执行成功")
                except sqlite3.Error as e:
                    logger.error(f"✗ {sql_file} 执行失败: {e}")
                    conn.rollback()
                    raise
        else:
            logger.warning(f"SQL文件不存在: {sql_file}")
    
    conn.close()
    logger.info("数据库初始化完成")


def reset_database():
    """重置数据库"""
    db_path = get_database_path()
    if db_path.exists():
        db_path.unlink()
        logger.info(f"已删除数据库: {db_path}")
    init_database(force=False)


def backup_database(backup_path: Path = None):
    """备份数据库"""
    import shutil
    import datetime
    
    db_path = get_database_path()
    if not db_path.exists():
        logger.warning("数据库不存在，无法备份")
        return None
    
    if backup_path is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.parent / f"flood_control_backup_{timestamp}.db"
    
    shutil.copy2(str(db_path), str(backup_path))
    logger.info(f"数据库已备份到: {backup_path}")
    return backup_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        init_database(force=True)
    else:
        init_database()
