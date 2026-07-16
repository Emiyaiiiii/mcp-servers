import os
import platform
import subprocess
from contextlib import contextmanager
from typing import List, Optional, Tuple
import pyodbc
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_dispatch_mdb_path():
    """获取调度 MDB 数据库文件路径"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    dispatch_dir = os.path.join(project_root, 'src', 'services', 'external_api', 'RegualDispacth')
    return os.path.join(dispatch_dir, '6', 'data.mdb')


def get_mdb_driver_name():
    """根据系统自动选择 MDB 驱动"""
    if platform.system() == "Windows":
        return "Microsoft Access Driver (*.mdb, *.accdb)"
    return "MDBTools"


@contextmanager
def get_mdb_connection(mdb_path: Optional[str] = None):
    """MDB 数据库连接上下文管理器，自动处理驱动选择和连接关闭"""
    if mdb_path is None:
        mdb_path = get_dispatch_mdb_path()
    driver_name = get_mdb_driver_name()
    conn_str = f'DRIVER={{{driver_name}}};DBQ={mdb_path};'
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        yield conn.cursor(), conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def mdb_execute(cursor, sql: str, params: tuple = None):
    """Execute SQL on MDB database, compatible with MDBTools driver that doesn't support SQLNumParams."""
    if params:
        escaped_params = []
        for p in params:
            if p is None:
                escaped_params.append("NULL")
            elif isinstance(p, float):
                if p == int(p):
                    escaped_params.append(str(int(p)))
                else:
                    escaped_params.append(str(p))
            elif isinstance(p, int):
                escaped_params.append(str(p))
            elif isinstance(p, str):
                escaped_p = p.replace("'", "''")
                escaped_params.append(f"'{escaped_p}'")
            else:
                escaped_p = str(p).replace("'", "''")
                escaped_params.append(f"'{escaped_p}'")

        parts = sql.split('?')
        if len(parts) - 1 != len(escaped_params):
            raise ValueError(
                f"Parameter count mismatch: SQL has {len(parts)-1} placeholders, got {len(escaped_params)} params"
            )

        result_sql = ""
        for i, part in enumerate(parts):
            result_sql += part
            if i < len(escaped_params):
                result_sql += escaped_params[i]

        logger.debug(f"mdb_execute SQL: {result_sql}")
        return cursor.execute(result_sql)
    else:
        return cursor.execute(sql)


def mdb_update_field(mdb_path: str, table_name: str, column_name: str, new_value: float, key_column: str, key_value: int):
    """Update a numeric field in an MDB table using the compiled mdb_update helper."""
    helper_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                               "src", "services", "external_api", "RegualDispacth", "c", "mdb_update")
    if platform.system() == "Windows":
        helper_path += ".exe"

    if not os.path.exists(helper_path):
        raise FileNotFoundError(f"mdb_update helper not found: {helper_path}")

    cmd = [helper_path, mdb_path, table_name, column_name, str(new_value), key_column, str(key_value)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mdb_update failed: {result.stderr.strip() or result.stdout.strip()}")
    return True


def mdb_clear_table(mdb_path: str, table_name: str):
    """Delete all rows from an MDB table using the compiled mdb_clear_table helper."""
    helper_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                               "src", "services", "external_api", "RegualDispacth", "c", "mdb_clear_table")
    if platform.system() == "Windows":
        helper_path += ".exe"

    if not os.path.exists(helper_path):
        raise FileNotFoundError(f"mdb_clear_table helper not found: {helper_path}")

    cmd = [helper_path, mdb_path, table_name]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mdb_clear_table failed: {result.stderr.strip() or result.stdout.strip()}")
    return True


def mdb_insert_rows(mdb_path: str, table_name: str, rows: list):
    """Insert multiple rows into an MDB table using the compiled mdb_insert_row helper."""
    helper_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                               "src", "services", "external_api", "RegualDispacth", "c", "mdb_insert_row")
    if platform.system() == "Windows":
        helper_path += ".exe"

    if not os.path.exists(helper_path):
        raise FileNotFoundError(f"mdb_insert_row helper not found: {helper_path}")

    tsv_data = "\n".join("\t".join(str(v) for v in row) for row in rows)
    result = subprocess.run([helper_path, mdb_path, table_name],
                           input=tsv_data, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"mdb_insert_row failed: {result.stderr.strip() or result.stdout.strip()}")
    return True
