"""验证 Q_Output 数据确实由 RegualDispacth.exe 生成"""
import pyodbc
import subprocess
import os
import time

MDB_PATH = r'D:\code\mcp-servers\6\data.mdb'
EXE_PATH = r'D:\code\mcp-servers\RegualDispacth.exe'
PROJECT_ROOT = r'D:\code\mcp-servers'


def get_row_count(cursor, table):
    cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
    return cursor.fetchone()[0]


def get_preview(cursor, table, n=3):
    cursor.execute(f'SELECT TOP {n} * FROM [{table}] ORDER BY tm')
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description] if cursor.description else []
    result = []
    for row in rows:
        result.append(dict(zip(cols, row)))
    return result


def main():
    print("=" * 70)
    print("  验证 Q_Output 数据由 RegualDispacth.exe 生成")
    print("=" * 70)

    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
    conn = pyodbc.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()

    # ─── 步骤1: 查看当前状态 ────────────────────────────────────────
    print()
    print("  步骤 1: 查看当前各表行数（初始状态）")
    print("  " + "-" * 50)
    for t in ['Q_Inputsd', 'Q_Inputxd', 'Q_Output']:
        cnt = get_row_count(cursor, t)
        print(f"  {t}: {cnt} 行")

    # ─── 步骤2: 清空 Q_Output ────────────────────────────────────────
    print()
    print("  步骤 2: 清空 Q_Output 表")
    print("  " + "-" * 50)
    before_clear = get_row_count(cursor, 'Q_Output')
    print(f"  清空前 Q_Output: {before_clear} 行")
    cursor.execute('DELETE FROM [Q_Output]')
    after_clear = get_row_count(cursor, 'Q_Output')
    print(f"  清空后 Q_Output: {after_clear} 行")
    assert after_clear == 0, "清空失败！"
    print("  ✅ Q_Output 已确认为 0 行")

    # ─── 步骤3: 运行 exe ────────────────────────────────────────
    print()
    print("  步骤 3: 运行 RegualDispacth.exe")
    print("  " + "-" * 50)
    print(f"  EXE 路径: {EXE_PATH}")
    print(f"  工作目录: {PROJECT_ROOT}")
    print("  运行中...")

    start = time.time()
    result = subprocess.run(
        [EXE_PATH],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=300
    )
    elapsed = round(time.time() - start, 2)

    print(f"  退出码: {result.returncode}")
    print(f"  耗时: {elapsed} 秒")
    if result.stdout:
        print(f"  stdout: {result.stdout[:200]}")
    if result.stderr:
        print(f"  stderr: {result.stderr[:200]}")

    if result.returncode != 0:
        print("  ⚠️  退出码非 0，但继续检查数据...")

    # ─── 步骤4: 验证 Q_Output 数据 ───────────────────────────────
    print()
    print("  步骤 4: 验证 Q_Output 表数据")
    print("  " + "-" * 50)
    after_exe = get_row_count(cursor, 'Q_Output')
    print(f"  exe 运行后 Q_Output: {after_exe} 行")

    if after_exe > 0:
        print("  ✅ Q_Output 有数据，证明确实由 exe 生成！")
        preview = get_preview(cursor, 'Q_Output')
        print(f"  前 3 行预览:")
        for i, row in enumerate(preview):
            clean = {k: v for k, v in list(row.items())[:4]}
            print(f"    {i+1}. {clean}")
    else:
        print("  ❌ Q_Output 仍为 0 行，exe 未生成数据")

    # ─── 步骤5: 同时验证两个 input 表数据未被破坏 ────────────────────
    print()
    print("  步骤 5: 验证 Input 表数据完整性")
    print("  " + "-" * 50)
    for t in ['Q_Inputsd', 'Q_Inputxd']:
        cnt = get_row_count(cursor, t)
        print(f"  {t}: {cnt} 行")

    conn.close()

    print()
    print("=" * 70)
    if after_exe > 0 and result.returncode == 0:
        print("  ✅✅✅ 结论: Q_Output 数据确实由 RegualDispacth.exe 生成！")
    elif after_exe > 0:
        print("  ✅ 结论: Q_Output 有数据生成（退出码非0但有输出）")
    else:
        print("  ❌ 结论: 验证失败")
    print("=" * 70)


if __name__ == "__main__":
    main()
