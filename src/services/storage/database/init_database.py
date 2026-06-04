import sqlite3
import re
from pathlib import Path
from src.services.storage.database import get_database_path
from src.utils.logger import get_logger

logger = get_logger(__name__)

_database_initialized = False


def _import_rainfall_data(conn, sql_path):
    """批量导入雨量数据"""
    logger.info("开始批量导入雨量数据...")
    
    with open(sql_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    data = []
    current_values = None
    
    for line in lines:
        if line.startswith('INSERT OR IGNORE INTO rainfall_hourly'):
            current_values = []
        elif line.strip().startswith('VALUES (') and current_values is not None:
            values_str = line.strip().replace('VALUES (', '').replace(');', '')
            values = values_str.split(',')
            try:
                row = (
                    values[0].strip().strip("'"),
                    values[1].strip().strip("'"),
                    values[2].strip().strip("'"),
                    float(values[3].strip()),
                    int(values[4].strip()),
                    values[5].strip().strip("'"),
                    values[6].strip().strip("'"),
                    float(values[7].strip()),
                    float(values[8].strip()),
                    values[9].strip().strip("'")
                )
                data.append(row)
            except Exception as e:
                continue
    
    cursor = conn.cursor()
    sql = """INSERT OR IGNORE INTO rainfall_hourly 
(station_code, station_name, timestamp, rainfall, step, river_name, water_system, longitude, latitude, reservoir_code)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    
    total = len(data)
    batch_size = 10000
    inserted = 0
    
    for i in range(0, total, batch_size):
        batch = data[i:i+batch_size]
        cursor.executemany(sql, batch)
        conn.commit()
        inserted += len(batch)
        logger.info(f"雨量数据导入进度: {inserted}/{total} ({inserted/total*100:.1f}%)")
    
    logger.info(f"✓ 雨量数据导入完成，共 {inserted} 条记录")


def init_database(force: bool = False):
    """初始化数据库
    
    Args:
        force: 是否强制重建数据库
    """
    global _database_initialized
    
    if _database_initialized and not force:
        return
    
    db_path = get_database_path()
    sql_dir = Path(__file__).parent.parent.parent.parent.parent / "sql"
    
    logger.info(f"初始化数据库: {db_path}")
    logger.info(f"SQL目录: {sql_dir}")
    
    if db_path.exists() and not force:
        logger.info("数据库已存在，跳过初始化")
        _database_initialized = True
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    sql_files = [
        "01_create_tables.sql",
        "02_seed_reservoirs.sql",
        "01c_seed_hydrology_weight.sql",
        "03_seed_water_levels.sql",
        "04_seed_simulation_params.sql",
        "05_seed_flood_plan.sql",
        "06_seed_dispatch_schemes.sql",
        "07_seed_evacuation_data.sql",
        "07_seed_xinanjiang_config.sql",
        "08_create_rainfall_tables.sql"
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
    
    rainfall_sql = sql_dir / "09_seed_rainfall_data.sql"
    if rainfall_sql.exists():
        _import_rainfall_data(conn, rainfall_sql)
    
    conn.close()
    _database_initialized = True
    logger.info("数据库初始化完成")


def reset_database():
    """重置数据库"""
    global _database_initialized
    _database_initialized = False
    
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
