"""清空三个数据库表"""
import pyodbc

MDB_PATH = r'D:\code\mcp-servers\6\data.mdb'

conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("=" * 70)
print("  清空数据库表")
print("=" * 70)

for table in ['Q_Inputsd', 'Q_Inputxd', 'Q_Output']:
    cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
    count_before = cursor.fetchone()[0]
    print(f"  {table} 清空前: {count_before} 行")

    cursor.execute(f'DELETE FROM [{table}]')
    conn.commit()

    cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
    count_after = cursor.fetchone()[0]
    print(f"  {table} 清空后: {count_after} 行")

conn.close()
print("\n  ✅ 三个表已全部清空")