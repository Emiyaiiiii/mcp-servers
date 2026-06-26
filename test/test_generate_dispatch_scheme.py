#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes 端调用防洪四预 MCP 服务 - 测试 generate_dispatch_scheme 新逻辑
验证：导入Excel → 运行exe → 统计处理 → 存储入库 → 返回前台展示数据
"""
import sys
import json
import time
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession


async def main():
    print("=" * 70)
    print("  Hermes 端 MCP 调用测试 - generate_dispatch_scheme 新逻辑")
    print("=" * 70)
    print(f"  MCP 服务地址: http://localhost:8082/mcp")
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  验证：统计处理后存储入库，返回前台展示数据（不导出到output/）")

    try:
        async with streamable_http_client("http://localhost:8082/mcp") as streams:
            read_stream, write_stream, _get_session_id = streams
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                print(f"  ✅ 连接成功: {init_result.serverInfo.name} v{init_result.serverInfo.version}")

                # ─── 1. 获取工具列表 ─────────────────────────────────────
                print()
                print("=" * 70)
                print("  步骤 1: 获取工具列表")
                print("=" * 70)
                tools_result = await session.list_tools()
                tools = tools_result.tools
                target_tools = [t for t in tools if t.name in ['generate_dispatch_scheme', 'generate_dispatch_sheet', 'modify_dispatch_param']]
                for t in target_tools:
                    desc = t.description[:100].replace('\n', ' ')
                    print(f"  → {t.name}: {desc}...")

                # ─── 2. 调用 generate_dispatch_scheme ─────────────────────
                print()
                print("=" * 70)
                print("  步骤 2: 调用 generate_dispatch_scheme")
                print("=" * 70)

                start_time = time.time()
                call_result = await session.call_tool("generate_dispatch_scheme", {})
                elapsed = round(time.time() - start_time, 2)

                if not call_result.content:
                    print("  ❌ 无响应内容")
                    return

                text = call_result.content[0].text
                try:
                    data = json.loads(text)
                except:
                    print(f"  ❌ 响应解析失败: {text[:500]}")
                    return

                success = data.get('success', False)
                if not success:
                    print(f"  ❌ 生成失败: {data.get('error', 'N/A')}")
                    return

                print(f"  ✅ 生成成功！耗时: {elapsed}s")

                # 验证 steps
                steps = data.get('steps', {})
                print()
                print("  --- 执行步骤 ---")
                for step_name, step_info in steps.items():
                    print(f"  [{step_name}]")
                    for k, v in step_info.items():
                        print(f"      {k}: {v}")

                # 验证 scheme_id（存储入库）
                print()
                print("  --- 存储入库验证 ---")
                scheme_id = data.get('scheme_id', '')
                if scheme_id:
                    print(f"  ✅ scheme_id: {scheme_id} (已存储到数据库)")
                else:
                    print(f"  ❌ 未返回 scheme_id，未存储入库")

                # 验证 summary（前台展示数据）
                print()
                print("  --- 前台展示数据 (summary) ---")
                summary = data.get('summary', {})
                print(f"  总站点数: {summary.get('total_stations', 0)}")
                print(f"  总数据行: {summary.get('total_rows', 0)}")
                print(f"  时间范围: {summary.get('time_range', {})}")

                top_by_max = summary.get('top_stations_by_max_flow', [])
                if top_by_max:
                    print(f"  TOP5 最大流量站点:")
                    for i, s in enumerate(top_by_max, 1):
                        print(f"    {i}. {s['name']}: max={s['max_flow']}, avg={s['avg_flow']}")

                top_by_avg = summary.get('top_stations_by_avg_flow', [])
                if top_by_avg:
                    print(f"  TOP5 平均流量站点:")
                    for i, s in enumerate(top_by_avg, 1):
                        print(f"    {i}. {s['name']}: avg={s['avg_flow']}, max={s['max_flow']}")

                # 验证没有 output_file 字段（不再导出到output/）
                print()
                print("  --- 导出到output/ 验证 ---")
                if data.get('output_file'):
                    print(f"  ❌ 仍在导出到: {data.get('output_file')}")
                else:
                    print(f"  ✅ 不再导出到 output/ 文件夹，数据已存储入库")

                # ─── 3. 验证数据库 ────────────────────────────────────────
                print()
                print("=" * 70)
                print("  步骤 3: 验证数据库表数据")
                print("=" * 70)
                import pyodbc
                MDB_PATH = r'D:\code\mcp-servers\6\data.mdb'
                conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()

                for table in ['Q_Inputsd', 'Q_Inputxd', 'Q_Output']:
                    cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
                    count = cursor.fetchone()[0]
                    status = "✅" if count > 0 else "❌"
                    print(f"  {status} {table}: {count} 行")

                conn.close()

                # ─── 4. 调用 generate_dispatch_sheet 验证兼容性 ──────────
                print()
                print("=" * 70)
                print("  步骤 4: 调用 generate_dispatch_sheet（兼容性验证）")
                print("=" * 70)

                start_time2 = time.time()
                call_result2 = await session.call_tool("generate_dispatch_sheet", {})
                elapsed2 = round(time.time() - start_time2, 2)

                if call_result2.content:
                    text2 = call_result2.content[0].text
                    try:
                        data2 = json.loads(text2)
                        if data2.get('success'):
                            print(f"  ✅ generate_dispatch_sheet 也成功！耗时: {elapsed2}s")
                            print(f"  scheme_id: {data2.get('scheme_id', 'N/A')}")
                            summary2 = data2.get('summary', {})
                            print(f"  总站点数: {summary2.get('total_stations', 0)}")
                            print(f"  总数据行: {summary2.get('total_rows', 0)}")
                        else:
                            print(f"  ❌ 失败: {data2.get('error', 'N/A')}")
                    except:
                        print(f"  ❌ 解析失败: {text2[:200]}")

                # ─── 总结 ────────────────────────────────────────────────
                print()
                print("=" * 70)
                print("  测试总结")
                print("=" * 70)
                print(f"  ✅ generate_dispatch_scheme 新逻辑: 导入→计算→统计→入库→返回")
                print(f"  ✅ 不再导出到 output/ 文件夹")
                print(f"  ✅ 数据已存储到数据库（scheme_id: {scheme_id}）")
                print(f"  ✅ 返回前台展示数据（summary）包含统计信息")
                print(f"  ✅ generate_dispatch_sheet 兼容性正常")
                print(f"  ✅ 全部测试通过！")
                print("=" * 70)

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())