#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试参数模板工具的完整功能"""
import sys
import json
import time
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession


async def call_tool(session, tool_name, args={}):
    start = time.time()
    try:
        result = await session.call_tool(tool_name, args)
        elapsed = time.time() - start
        if result.content:
            text = result.content[0].text
            try:
                data = json.loads(text)
                return (True, data, elapsed)
            except:
                return (True, {"raw": text[:500]}, elapsed)
        return (True, {}, elapsed)
    except Exception as e:
        elapsed = time.time() - start
        return (False, {"error": str(e)}, elapsed)


async def main():
    print("=" * 70)
    print("  参数模板工具测试")
    print("=" * 70)

    async with streamable_http_client("http://localhost:8082/mcp") as streams:
        read_stream, write_stream, _get_session_id = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print(f"  ✅ 已连接\n")

            # ─── 1. list_parameter_templates ────────────────────────────
            print("=" * 70)
            print("  1. list_parameter_templates - 列出所有模板")
            print("=" * 70)
            ok, data, dur = await call_tool(session, "list_parameter_templates", {})
            if ok and data.get("success"):
                templates = data.get("templates", [])
                print(f"  ✅ 成功！共 {len(templates)} 个模板")
                for t in templates:
                    print(f"     [{t['category']}] {t['name']}: {t['param_count']}条参数, sheets={t['result_sheets']}")
            else:
                print(f"  ❌ 失败: {data.get('error', '')}")

            # ─── 2. show_parameter_template ─────────────────────────────
            print()
            print("=" * 70)
            print("  2. show_parameter_template - 展示方案一参数")
            print("=" * 70)
            ok, data, dur = await call_tool(session, "show_parameter_template", {"template_name": "方案一"})
            if ok and data.get("success"):
                params = data.get("parameters", [])
                tmpl = data.get("template", {})
                print(f"  ✅ 成功！{tmpl['name']} ({tmpl['category']})")
                print(f"     参数: {len(params)}条, 结果sheet: {tmpl['result_sheets']}")
                print(f"     前5条参数:")
                for p in params[:5]:
                    print(f"       stcd={p['stcd']}, stnm={p['stnm']}, Control_Par={p['Control_Par']}, Instruction={p['Instruction'][:40]}")
            else:
                print(f"  ❌ 失败: {data.get('error', '')}")
                if data.get("available_templates"):
                    print(f"     可用模板: {data['available_templates']}")

            # ─── 3. show_parameter_template - 模糊匹配 ──────────────────
            print()
            print("=" * 70)
            print("  3. show_parameter_template - 模糊匹配'常规调度'")
            print("=" * 70)
            ok, data, dur = await call_tool(session, "show_parameter_template", {"template_name": "常规调度"})
            if ok and data.get("success"):
                tmpl = data.get("template", {})
                print(f"  ✅ 成功！匹配到: {tmpl['name']} ({tmpl['category']})")
                print(f"     参数: {tmpl['param_count']}条, sheets: {tmpl['result_sheets']}")
            else:
                print(f"  ❌ 失败: {data.get('error', '')}")

            # ─── 4. show_parameter_template - 不存在的模板 ──────────────
            print()
            print("=" * 70)
            print("  4. show_parameter_template - 不存在的模板")
            print("=" * 70)
            ok, data, dur = await call_tool(session, "show_parameter_template", {"template_name": "不存在"})
            if not ok or not data.get("success"):
                print(f"  ✅ 正确返回错误: {data.get('error', '')}")
                if data.get("available_templates"):
                    print(f"     可用模板: {data['available_templates']}")
            else:
                print(f"  ⚠️  意外成功")

            # ─── 5. apply_parameter_template - 仅更新参数 ───────────────
            print()
            print("=" * 70)
            print("  5. apply_parameter_template - 仅更新参数(不生成方案)")
            print("=" * 70)
            ok, data, dur = await call_tool(session, "apply_parameter_template", {
                "template_name": "方案一", "generate_scheme": False
            })
            if ok and data.get("success"):
                print(f"  ✅ 成功！更新 {data['updated_count']} 条参数")
                print(f"     变更 {data['total_changed']} 条")
                if data.get("changed_params"):
                    for p in data["changed_params"][:3]:
                        print(f"       stcd={p['stcd']}: {p['old_value']} -> {p['new_value']} ({p['instruction']})")
            else:
                print(f"  ❌ 失败: {data.get('error', '')}")

            # ─── 6. verify Dispatch_Par 数据一致性 ───────────────────────
            print()
            print("=" * 70)
            print("  6. 验证 Dispatch_Par 表数据与模板一致")
            print("=" * 70)
            import pyodbc
            MDB_PATH = r'D:\code\mcp-servers\6\data.mdb'
            conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_PATH};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT stcd, Control_Par FROM Dispatch_Par ORDER BY stcd")
            db_values = {row.stcd: row.Control_Par for row in cursor.fetchall()}
            conn.close()

            import pandas as pd
            tmpl_path = r'D:\code\mcp-servers\Parameter_template\上大洪水控制\方案一：（小浪底不保滩，控花园口10000）.xlsx'
            df = pd.read_excel(tmpl_path, sheet_name='参数')
            match_count = 0
            mismatch = []
            for _, row in df.iterrows():
                stcd = row.get('stcd', '')
                ctrl = row.get('Control_Par', 0)
                if stcd in db_values:
                    if db_values[stcd] == ctrl:
                        match_count += 1
                    else:
                        mismatch.append((stcd, db_values[stcd], ctrl))
            if mismatch:
                print(f"  ❌ 不一致: {match_count}条匹配, {len(mismatch)}条不匹配")
                for m in mismatch[:3]:
                    print(f"     stcd={m[0]}: DB={m[1]} vs 模板={m[2]}")
            else:
                print(f"  ✅ Dispatch_Par 与模板完全一致！({match_count}条)")

            # ─── 7. apply_parameter_template - 应用并生成方案 ────────────
            print()
            print("=" * 70)
            print("  7. apply_parameter_template - 应用'常规调度'并生成方案")
            print("=" * 70)
            print("  ⏳ 运行中（6-7秒）...")
            ok, data, dur = await call_tool(session, "apply_parameter_template", {
                "template_name": "常规调度", "generate_scheme": True
            })
            if ok and data.get("success"):
                print(f"  ✅ 成功！耗时 {dur}s")
                print(f"     模板: {data['template_name']}")
                print(f"     更新: {data['updated_count']} 条参数")
                print(f"     scheme_id: {data.get('scheme_id', 'N/A')}")
                summary = data.get("summary", {})
                if summary:
                    print(f"     summary: {summary.get('total_stations', 0)}站点/{summary.get('total_rows', 0)}行")
            else:
                print(f"  ❌ 失败: {data.get('error', '')}")

            # ─── 8. verify_dispatch_result ──────────────────────────────
            print()
            print("=" * 70)
            print("  8. verify_dispatch_result - 验证'常规调度'计算结果")
            print("=" * 70)
            print("  ⏳ 运行中（6-7秒）...")
            ok, data, dur = await call_tool(session, "verify_dispatch_result", {
                "template_name": "常规调度"
            })
            if ok and data.get("success"):
                v = data.get("verification", {})
                print(f"  ✅ 验证完成！耗时 {dur}s")
                print(f"     状态: {v.get('status')}")
                print(f"     消息: {v.get('message')}")
                print(f"     匹配点数: {v.get('total_matched_points')}")
                print(f"     对比站点: {v.get('stations_compared')}")
                for sn, sd in v.get("station_details", {}).items():
                    print(f"     [{sn}] 匹配{sd['matched_points']}点, 最大偏差{sd['max_deviation_pct']}%, 平均偏差{sd['avg_deviation_pct']}%")
            else:
                print(f"  ❌ 失败: {data.get('error', '')}")

            # ─── 总结 ──────────────────────────────────────────────────
            print()
            print("=" * 70)
            print("  测试完成")
            print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())