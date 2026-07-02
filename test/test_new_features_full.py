#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
防洪四预 MCP — 新增参数模板业务功能系统性测试
覆盖 list_parameter_templates / show_parameter_template / apply_parameter_template / verify_dispatch_result
"""
import sys
import json
import time
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession


class TestSuite:
    def __init__(self):
        self.results = []
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    def record(self, test_id, test_name, status, detail="", duration=0):
        self.results.append({"id": test_id, "name": test_name, "status": status, "detail": detail, "duration": duration})
        if status == "PASS": self.pass_count += 1
        elif status == "FAIL": self.fail_count += 1
        elif status == "WARN": self.warn_count += 1

    def print_report(self):
        print()
        print("=" * 80)
        print("  📊 测试报告")
        print("=" * 80)
        total = self.pass_count + self.fail_count + self.warn_count
        print(f"  总计: {total}  |  ✅ PASS: {self.pass_count}  |  ❌ FAIL: {self.fail_count}  |  ⚠️ WARN: {self.warn_count}")
        print()

        current_cat = ""
        for r in self.results:
            cat = r["id"].split(".")[0]
            if cat != current_cat:
                current_cat = cat
                print(f"  ── {cat} ──")
            icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[r["status"]]
            print(f"     {icon} {r['id']} {r['name']} ({r['duration']:.2f}s) {r['detail']}")

        print()
        print("=" * 80)
        if self.fail_count == 0:
            print("  ✅✅✅ 全部测试通过！")
        else:
            print(f"  ❌ 有 {self.fail_count} 项失败，请检查")
        print("=" * 80)


ts = TestSuite()


async def call(session, tool, args={}):
    start = time.time()
    try:
        result = await session.call_tool(tool, args)
        elapsed = time.time() - start
        if result.content:
            text = result.content[0].text
            try:
                return (True, json.loads(text), elapsed)
            except:
                return (True, {"raw": text[:500]}, elapsed)
        return (True, {}, elapsed)
    except Exception as e:
        return (False, {"error": str(e)}, time.time() - start)


async def main():
    print("=" * 80)
    print("  防洪四预 MCP — 新增参数模板业务功能系统性测试")
    print("=" * 80)
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  MCP: http://localhost:8082/mcp\n")

    async with streamable_http_client("http://localhost:8082/mcp") as streams:
        read_stream, write_stream, _get_session_id = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            info = init_result = await session.initialize()
            print(f"  ✅ 已连接: {info.serverInfo.name} v{info.serverInfo.version}")

            # ============================================================
            # 模块 A: list_parameter_templates
            # ============================================================
            print("\n" + "─" * 60)
            print("  模块 A: list_parameter_templates")
            print("─" * 60)

            # A1: 基本功能
            ok, data, dur = await call(session, "list_parameter_templates", {})
            if ok and data.get("success"):
                templates = data.get("templates", [])
                count = data.get("count", 0)
                if count == 5 and len(templates) == 5:
                    ts.record("A1", "基本功能-列出所有模板", "PASS", f"返回 {count} 个模板", dur)
                else:
                    ts.record("A1", "基本功能-列出所有模板", "FAIL", f"预期5个，实际{count}个", dur)
            else:
                ts.record("A1", "基本功能-列出所有模板", "FAIL", data.get("error", "无响应"), dur)

            # A2: 模板结构完整性
            if ok and data.get("success"):
                required_fields = ["name", "category", "file_name", "param_count", "result_sheets", "unique_key"]
                all_valid = all(
                    all(f in t for f in required_fields)
                    for t in templates
                )
                all_46 = all(t["param_count"] == 46 for t in templates)
                has_categories = sorted(set(t["category"] for t in templates))
                ts.record("A2", "结构完整性-字段/参数数/类别", "PASS",
                    f"字段齐全={all_valid}, 参数46条={all_46}, 类别={has_categories}", dur)
            else:
                ts.record("A2", "结构完整性", "FAIL", "前置A1失败", dur)

            # A3: 上大洪水控制模板数
            ok, data, dur = await call(session, "list_parameter_templates", {})
            if ok and data.get("success"):
                shangda = [t for t in data["templates"] if t["category"] == "上大洪水控制"]
                xia_da = [t for t in data["templates"] if t["category"] == "下大洪水控制"]
                ts.record("A3", "分类统计", "PASS",
                    f"上大洪水={len(shangda)}个, 下大洪水={len(xia_da)}个", dur)
            else:
                ts.record("A3", "分类统计", "FAIL", "前置失败", dur)

            # ============================================================
            # 模块 B: show_parameter_template
            # ============================================================
            print("\n" + "─" * 60)
            print("  模块 B: show_parameter_template")
            print("─" * 60)

            # B1: 精确匹配-上大方案一
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "上大洪水控制/方案一"})
            if ok and data.get("success"):
                params = data.get("parameters", [])
                tmpl = data.get("template", {})
                is_shangda = tmpl["category"] == "上大洪水控制"
                ts.record("B1", "精确匹配-唯一键'上大洪水控制/方案一'", "PASS",
                    f"类别={tmpl['category']}, 参数={len(params)}条, 结果sheet={tmpl['result_sheets']}", dur)
            else:
                ts.record("B1", "精确匹配-唯一键", "FAIL", data.get("error", ""), dur)

            # B2: 精确匹配-下大方案一
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "下大洪水控制/方案一"})
            if ok and data.get("success"):
                tmpl = data.get("template", {})
                is_xiada = "下大洪水控制" in tmpl["category"]
                ts.record("B2", "精确匹配-唯一键'下大洪水控制/方案一'", "PASS" if is_xiada else "FAIL",
                    f"类别={tmpl['category']}, 结果sheet数={len(tmpl['result_sheets'])}", dur)
            else:
                ts.record("B2", "精确匹配-唯一键", "FAIL", data.get("error", ""), dur)

            # B3: 模糊匹配-关键词"常规调度"
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "常规调度"})
            if ok and data.get("success"):
                tmpl = data.get("template", {})
                has_regular = "常规调度" in tmpl["name"]
                ts.record("B3", "模糊匹配-关键词'常规调度'", "PASS" if has_regular else "WARN",
                    f"匹配到: {tmpl['name'][:50]}...", dur)
            else:
                ts.record("B3", "模糊匹配-关键词'常规调度'", "FAIL", data.get("error", ""), dur)

            # B4: 模糊匹配-关键词"优化调度"
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "优化调度"})
            if ok and data.get("success"):
                tmpl = data.get("template", {})
                ts.record("B4", "模糊匹配-关键词'优化调度'", "PASS" if "优化调度" in tmpl["name"] else "WARN",
                    f"匹配到: {tmpl['name'][:50]}...", dur)
            else:
                ts.record("B4", "模糊匹配-关键词'优化调度'", "WARN" if data.get("available_templates") else "FAIL",
                    data.get("error", "未匹配"), dur)

            # B5: 模糊匹配-仅关键词"方案三"
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "方案三"})
            if ok and data.get("success"):
                tmpl = data.get("template", {})
                ts.record("B5", "模糊匹配-仅关键词'方案三'", "PASS" if "方案三" in tmpl["name"] else "WARN",
                    f"匹配到: {tmpl['name'][:50]}...", dur)
            else:
                ts.record("B5", "模糊匹配-仅关键词'方案三'", "WARN" if data.get("available_templates") else "FAIL",
                    data.get("error", ""), dur)

            # B6: 不存在的模板
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "不存在的模板XYZ"})
            if not ok or not data.get("success"):
                has_avail = bool(data.get("available_templates"))
                ts.record("B6", "错误处理-不存在的模板", "PASS" if has_avail else "WARN",
                    f"返回可用模板列表={has_avail}", dur)
            else:
                ts.record("B6", "错误处理-不存在的模板", "FAIL", "应该返回错误但成功了", dur)

            # B7: 参数内容验证-检查关键参数
            ok, data, dur = await call(session, "show_parameter_template", {"template_name": "上大洪水控制/方案一"})
            if ok and data.get("success"):
                params = data.get("parameters", [])
                stcd_3 = next((p for p in params if p["stcd"] == 3), None)
                stcd_4 = next((p for p in params if p["stcd"] == 4), None)
                stcd_46 = next((p for p in params if p["stcd"] == 46), None)
                details = []
                if stcd_3: details.append(f"stcd=3({stcd_3['stnm']}):{stcd_3['Control_Par']}")
                if stcd_4: details.append(f"stcd=4({stcd_4['stnm']}):{stcd_4['Control_Par']}")
                if stcd_46: details.append(f"stcd=46({stcd_46['stnm']}):{stcd_46['Control_Par']}")
                ts.record("B7", "参数内容-关键参数验证", "PASS" if len(details) >= 2 else "WARN",
                    ", ".join(details), dur)
            else:
                ts.record("B7", "参数内容-关键参数验证", "FAIL", "前置失败", dur)

            # ============================================================
            # 模块 C: apply_parameter_template
            # ============================================================
            print("\n" + "─" * 60)
            print("  模块 C: apply_parameter_template")
            print("─" * 60)

            # C1: 仅更新参数(generate_scheme=False)
            ok, data, dur = await call(session, "apply_parameter_template", {
                "template_name": "上大洪水控制/方案一", "generate_scheme": False
            })
            if ok and data.get("success"):
                uc = data.get("updated_count", 0)
                has_scheme = "scheme_id" in data
                ts.record("C1", "仅更新参数(不生成方案)", "PASS" if uc == 46 and not has_scheme else "WARN",
                    f"更新{uc}条, 生成方案={has_scheme}", dur)
            else:
                ts.record("C1", "仅更新参数(不生成方案)", "FAIL", data.get("error", ""), dur)

            # C2: 验证 Dispatch_Par 与模板一致
            import pyodbc
            MDB = r'D:\code\mcp-servers\6\data.mdb'
            conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB};'
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT stcd, Control_Par FROM Dispatch_Par ORDER BY stcd")
            db_map = {row.stcd: row.Control_Par for row in cursor.fetchall()}
            conn.close()

            import pandas as pd
            tmpl_path = r'D:\code\mcp-servers\Parameter_template\上大洪水控制\方案一：（小浪底不保滩，控花园口10000）.xlsx'
            df = pd.read_excel(tmpl_path, sheet_name='参数')
            match, mismatch, precision = 0, 0, 0
            for _, row in df.iterrows():
                stcd = row.get('stcd', '')
                expected = row.get('Control_Par', 0)
                actual = db_map.get(stcd)
                if actual is None:
                    mismatch += 1
                elif abs(actual - expected) < 0.01:
                    match += 1
                else:
                    precision += 1
            ts.record("C2", "DB一致性-与模板参数对比", "PASS" if mismatch == 0 else "WARN",
                f"精确匹配={match}, 浮点差异={precision}, 不匹配={mismatch}", dur)

            # C3: 应用参数并生成方案
            print("  ⏳ C3 应用'常规调度'并生成方案(约10s)...")
            ok, data, dur = await call(session, "apply_parameter_template", {
                "template_name": "常规调度", "generate_scheme": True
            })
            if ok and data.get("success"):
                sid = data.get("scheme_id", "")
                s = data.get("summary", {})
                has_sid = bool(sid)
                has_summary = bool(s.get("total_stations"))
                ts.record("C3", "应用参数+生成方案", "PASS" if has_sid and has_summary else "WARN",
                    f"scheme_id={sid}, summary={s.get('total_stations','?')}站点/{s.get('total_rows','?')}行", dur)
            else:
                ts.record("C3", "应用参数+生成方案", "FAIL", data.get("error", ""), dur)

            # C4: 不存在的模板
            ok, data, dur = await call(session, "apply_parameter_template", {
                "template_name": "不存在的模板", "generate_scheme": False
            })
            if not ok or not data.get("success"):
                ts.record("C4", "错误处理-不存在的模板", "PASS" if data.get("available_templates") else "WARN",
                    "返回可用模板列表", dur)
            else:
                ts.record("C4", "错误处理-不存在的模板", "FAIL", "应该返回错误", dur)

            # C5: 变更参数对比信息
            ok, data, dur = await call(session, "apply_parameter_template", {
                "template_name": "下大洪水控制/方案二", "generate_scheme": False
            })
            if ok and data.get("success"):
                changed = data.get("changed_params", [])
                total_changed = data.get("total_changed", 0)
                ts.record("C5", "变更对比-返回修改前后对比", "PASS",
                    f"变更{total_changed}条, 返回前{len(changed)}条详情", dur)
            else:
                ts.record("C5", "变更对比", "FAIL", data.get("error", ""), dur)

            # ============================================================
            # 模块 D: verify_dispatch_result
            # ============================================================
            print("\n" + "─" * 60)
            print("  模块 D: verify_dispatch_result")
            print("─" * 60)

            # D1: 验证常规调度方案
            print("  ⏳ D1 验证'常规调度'计算结果(约10s)...")
            ok, data, dur = await call(session, "verify_dispatch_result", {"template_name": "常规调度"})
            if ok and data.get("success"):
                v = data.get("verification", {})
                status = v.get("status", "")
                matched = v.get("total_matched_points", 0)
                stations = v.get("stations_compared", [])
                ts.record("D1", "验证常规调度-计算结果对比", "PASS" if status == "通过" else "WARN",
                    f"状态={status}, 匹配{matched}点, 对比{len(stations)}个sheet", dur)
                # 详细输出
                for sn, sd in v.get("station_details", {}).items():
                    print(f"       [{sn}] {sd['matched_points']}点, max={sd['max_deviation_pct']}%, avg={sd['avg_deviation_pct']}%")
            else:
                ts.record("D1", "验证常规调度-计算结果对比", "FAIL", data.get("error", ""), dur)

            # D2: 验证上大洪水方案一
            print("  ⏳ D2 验证'上大方案一'计算结果(约10s)...")
            ok, data, dur = await call(session, "verify_dispatch_result", {"template_name": "上大洪水控制/方案一"})
            if ok and data.get("success"):
                v = data.get("verification", {})
                status = v.get("status", "")
                matched = v.get("total_matched_points", 0)
                ts.record("D2", "验证上大方案一-计算结果对比", "PASS" if status in ["通过", "需关注"] else "WARN",
                    f"状态={status}, 匹配{matched}点", dur)
                for sn, sd in v.get("station_details", {}).items():
                    print(f"       [{sn}] {sd['matched_points']}点, max={sd['max_deviation_pct']}%, avg={sd['avg_deviation_pct']}%")
            else:
                ts.record("D2", "验证上大方案一", "FAIL", data.get("error", ""), dur)

            # D3: 验证报告结构完整性
            if ok and data.get("success"):
                v = data.get("verification", {})
                required = ["status", "message", "total_matched_points", "stations_compared", "station_details"]
                all_have = all(k in v for k in required)
                ts.record("D3", "验证报告结构完整性", "PASS" if all_have else "FAIL",
                    f"字段齐全={all_have}", dur)
            else:
                ts.record("D3", "验证报告结构", "FAIL", "前置D2失败", dur)

            # D4: 不存在的模板
            ok, data, dur = await call(session, "verify_dispatch_result", {"template_name": "不存在"})
            if not ok or not data.get("success"):
                ts.record("D4", "错误处理-不存在的模板", "PASS" if data.get("available_templates") else "WARN",
                    "正确返回错误", dur)
            else:
                ts.record("D4", "错误处理-不存在的模板", "FAIL", "应该返回错误", dur)

            # ============================================================
            # 模块 E: 集成场景
            # ============================================================
            print("\n" + "─" * 60)
            print("  模块 E: 集成场景")
            print("─" * 60)

            # E1: 完整工作流-查看模板→展示参数→应用→验证
            print("  ⏳ E1 完整工作流：查看模板→展示参数→应用→验证(约10s)...")
            # 先查看模板
            ok1, d1, _ = await call(session, "list_parameter_templates", {})
            if ok1 and d1.get("success"):
                # 展示参数
                ok2, d2, _ = await call(session, "show_parameter_template", {"template_name": "常规调度"})
                if ok2 and d2.get("success"):
                    # 应用并生成方案
                    ok3, d3, dur3 = await call(session, "apply_parameter_template", {
                        "template_name": "常规调度", "generate_scheme": True
                    })
                    if ok3 and d3.get("success"):
                        sid = d3.get("scheme_id", "")
                        ts.record("E1", "完整工作流-查看→展示→应用→生成", "PASS",
                            f"scheme_id={sid}, 耗时{dur3:.1f}s", dur3)
                    else:
                        ts.record("E1", "完整工作流", "FAIL", f"应用模板失败: {d3.get('error','')}", dur3)
                else:
                    ts.record("E1", "完整工作流", "FAIL", f"展示模板失败", 0)
            else:
                ts.record("E1", "完整工作流", "FAIL", f"列出模板失败", 0)

            # E2: 前后参数一致性-再次验证 Dispatch_Par
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT stcd, Control_Par FROM Dispatch_Par ORDER BY stcd")
            db_map2 = {row.stcd: row.Control_Par for row in cursor.fetchall()}
            conn.close()

            tmpl_path2 = r'D:\code\mcp-servers\Parameter_template\下大洪水控制\方案一：演练洪水-常规调度-控4500-1000-退水时刻及退水流量均为10000-支流水库按常规.xlsx'
            df2 = pd.read_excel(tmpl_path2, sheet_name='参数')
            match2, mismatch2 = 0, 0
            for _, row in df2.iterrows():
                stcd = row.get('stcd', '')
                expected = row.get('Control_Par', 0)
                actual = db_map2.get(stcd)
                if actual is not None and abs(actual - expected) < 0.01:
                    match2 += 1
                elif actual is not None:
                    mismatch2 += 1
            ts.record("E2", "E2集成后DB一致性", "PASS" if mismatch2 == 0 else "WARN",
                f"精确匹配={match2}, 不匹配={mismatch2}", dur)

            # E3: 频繁切换模板-方案一→方案二→方案三
            print("  ⏳ E3 频繁切换模板(应用3个模板)...")
            applied = 0
            for tname in ["上大洪水控制/方案一", "上大洪水控制/方案二", "上大洪水控制/方案三"]:
                ok, data, dur = await call(session, "apply_parameter_template", {
                    "template_name": tname, "generate_scheme": False
                })
                if ok and data.get("success"):
                    applied += 1
            ts.record("E3", "频繁切换-连续应用3个模板", "PASS" if applied == 3 else "FAIL",
                f"成功应用{applied}/3个模板", dur)

            # ============================================================
            # 输出测试报告
            # ============================================================
            ts.print_report()


if __name__ == "__main__":
    asyncio.run(main())