"""清空 Q_Inputsd 和 Q_Inputxd 表，然后运行测试"""
import pyodbc
import asyncio
import json
import sys
import time
from datetime import datetime

sys.path.insert(0, 'D:/code/mcp-servers/src')
from src.tools.forecast_models import register_forecast_models
from fastmcp import FastMCP

MDB_PATH = r'D:\code\mcp-servers\6\data.mdb'


def clear_tables():
    """清空 Q_Inputsd 和 Q_Inputxd 表"""
    print("=" * 70)
    print("  步骤 1: 清空数据库表")
    print("=" * 70)

    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

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
    print("  ✅ 表已清空")
    return True


async def run_test():
    """运行测试"""
    print("\n" + "=" * 70)
    print("  步骤 2: 运行 generate_dispatch_sheet 测试")
    print("=" * 70)

    mcp = FastMCP('test')
    register_forecast_models(mcp)

    # 测试: 生成调度方案单
    start = time.time()
    result = await mcp.call_tool('generate_dispatch_sheet', {})
    duration = round((time.time() - start) * 1000, 2)

    sc = result.structured_content
    success = sc.get('success', False)

    print(f"  状态: {'✅ 成功' if success else '❌ 失败'}")
    print(f"  总耗时: {duration}ms ({duration/1000:.2f}s)")

    if success:
        steps = sc.get('steps', {})
        for step_name, step_info in steps.items():
            print(f"  - {step_name}:")
            for k, v in step_info.items():
                print(f"      {k}: {v}")

        print(f"  输出文件: {sc.get('output_file', 'N/A')}")
    else:
        print(f"  错误: {sc.get('error', 'N/A')}")

    return sc


def verify_output():
    """验证 Q_Output 表的数据"""
    print("\n" + "=" * 70)
    print("  步骤 3: 验证数据库输出表")
    print("=" * 70)

    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    for table in ['Q_Inputsd', 'Q_Inputxd', 'Q_Output']:
        cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
        count = cursor.fetchone()[0]

        cursor.execute(f'SELECT TOP 1 * FROM [{table}]')
        cols = [c[0] for c in cursor.description] if cursor.description else []
        row = cursor.fetchone()

        print(f"  {table}: {count} 行")
        if row:
            print(f"    列: {cols}")
            print(f"    首行: {dict(zip(cols, row))}")

    conn.close()


async def main():
    print("\n" + "=" * 70)
    print("  清空表后测试 - 调度方案单生成")
    print(f"  测试时间: {datetime.now().isoformat()}")
    print("=" * 70)

    # 1. 清空表
    clear_tables()

    # 2. 运行测试
    result = await run_test()

    # 3. 验证输出
    verify_output()

    # 总结
    print("\n" + "=" * 70)
    print("  测试总结")
    print("=" * 70)
    success = result.get('success', False)
    print(f"  结果: {'✅ 通过' if success else '❌ 失败'}")
    if success:
        steps = result.get('steps', {})
        import_rows = steps.get('import', {}).get('Q_Inputsd_rows', 0) + steps.get('import', {}).get('Q_Inputxd_rows', 0)
        calc_time = steps.get('calculation', {}).get('elapsed_seconds', 0)
        export_rows = steps.get('export', {}).get('output_rows', 0)
        print(f"  导入数据: {import_rows} 行")
        print(f"  计算耗时: {calc_time}s")
        print(f"  导出数据: {export_rows} 行")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())