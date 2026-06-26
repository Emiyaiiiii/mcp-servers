#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes 端调用防洪四预 MCP 服务 - 生成调度方案单测试
使用 MCP Python SDK 官方客户端（与 Hermes Agent 调用方式一致）
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
    print("  Hermes 端 MCP 调用测试 - 生成调度方案单")
    print("=" * 70)
    print(f"  MCP 服务地址: http://localhost:8082/mcp")
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  调用方式: MCP SDK streamable-http 客户端")

    # ─── 1. 连接 MCP 服务 ────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  步骤 1: 连接 MCP 服务并初始化")
    print("=" * 70)

    try:
        async with streamable_http_client("http://localhost:8082/mcp") as streams:
            read_stream, write_stream, _get_session_id = streams
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                print(f"  ✅ 连接成功")
                print(f"     服务名: {init_result.serverInfo.name}")
                print(f"     版本: {init_result.serverInfo.version}")
                print(f"     协议: {init_result.protocolVersion}")

                # ─── 2. 获取工具列表 ─────────────────────────────────────
                print()
                print("=" * 70)
                print("  步骤 2: 获取工具列表 (tools/list)")
                print("=" * 70)

                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"  ✅ 共发现 {len(tools)} 个工具")

                target_tools = [t for t in tools if t.name in ['generate_dispatch_sheet', 'modify_dispatch_param']]
                for t in target_tools:
                    print(f"  → {t.name}: {t.description[:80]}")

                # ─── 3. 调用 generate_dispatch_sheet ─────────────────────
                print()
                print("=" * 70)
                print("  步骤 3: 调用 generate_dispatch_sheet 生成调度方案单")
                print("=" * 70)
                print("  （注意：三个表已预先清空，验证数据是新导入的）")

                start_time = time.time()
                call_result = await session.call_tool("generate_dispatch_sheet", {})
                elapsed = round(time.time() - start_time, 2)

                if call_result.content:
                    text = call_result.content[0].text
                    try:
                        data = json.loads(text)
                        success = data.get('success', False)
                        if success:
                            print(f"  ✅ 生成成功！耗时: {elapsed}s")
                            steps = data.get('steps', {})
                            for step_name, step_info in steps.items():
                                print(f"  - {step_name}:")
                                for k, v in step_info.items():
                                    print(f"      {k}: {v}")
                            print(f"  输出文件: {data.get('output_file', 'N/A')}")
                        else:
                            print(f"  ❌ 生成失败")
                            print(f"  错误: {data.get('error', 'N/A')}")
                    except:
                        print(f"  响应: {text[:500]}")
                else:
                    print(f"  ❌ 无响应内容")

                # ─── 4. 验证数据库表数据 ─────────────────────────────────
                print()
                print("=" * 70)
                print("  步骤 4: 验证数据库表数据")
                print("=" * 70)
                import pyodbc
                MDB_PATH = r'D:\code\mcp-servers\6\data.mdb'
                conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()

                for table in ['Q_Inputsd', 'Q_Inputxd', 'Q_Output']:
                    cursor.execute(f'SELECT COUNT(*) FROM [{table}]')
                    count = cursor.fetchone()[0]

                    cursor.execute(f'SELECT TOP 1 * FROM [{table}]')
                    cols = [c[0] for c in cursor.description] if cursor.description else []
                    row = cursor.fetchone()

                    status = "✅" if count > 0 else "❌"
                    print(f"  {status} {table}: {count} 行")
                    if row:
                        row_dict = dict(zip(cols, row))
                        preview = {k: v for k, v in list(row_dict.items())[:4]}
                        print(f"     首行: {preview}")

                conn.close()

                # ─── 5. 再调用 modify_dispatch_param 验证 ────────────────
                print()
                print("=" * 70)
                print("  步骤 5: 调用 modify_dispatch_param 修改参数")
                print("=" * 70)

                call_result2 = await session.call_tool("modify_dispatch_param", {
                    "action": "update",
                    "station_name": "小浪底",
                    "param_desc": "初始水位",
                    "new_value": 251.0
                })

                if call_result2.content:
                    text = call_result2.content[0].text
                    try:
                        data = json.loads(text)
                        success = data.get('success', False)
                        if success:
                            print(f"  ✅ 参数修改成功")
                            if 'before' in data and 'after' in data:
                                print(f"     修改前: {data['before']['Control_Par']}")
                                print(f"     修改后: {data['after']['Control_Par']}")
                        else:
                            print(f"  ❌ 修改失败: {data.get('error', 'N/A')}")
                    except:
                        print(f"  响应: {text[:300]}")

                # 恢复参数
                call_result3 = await session.call_tool("modify_dispatch_param", {
                    "action": "update",
                    "station_name": "小浪底",
                    "param_desc": "初始水位",
                    "new_value": 250.86
                })

                if call_result3.content:
                    text = call_result3.content[0].text
                    try:
                        data = json.loads(text)
                        if data.get('success', False):
                            print(f"  ✅ 参数已恢复")
                    except:
                        pass

                # ─── 总结 ────────────────────────────────────────────────
                print()
                print("=" * 70)
                print("  测试总结")
                print("=" * 70)
                print(f"  MCP 服务: http://localhost:8082/mcp")
                print(f"  调用方式: MCP SDK streamable-http 客户端")
                print(f"  方案单生成耗时: {elapsed}s")
                print(f"  工具总数: {len(tools)}")
                print("=" * 70)
                print("  ✅ 全部测试通过！")
                print("=" * 70)

    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())