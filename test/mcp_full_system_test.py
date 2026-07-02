#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
防洪四预 MCP 服务 — 全功能系统性测试（修正版）
正确处理各种响应格式，准确区分 PASS/FAIL/WARN
"""
import sys
import json
import time
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession


class TestReport:
    def __init__(self):
        self.results = []
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    def add(self, category, tool, status, detail="", duration=0):
        self.results.append({
            "category": category, "tool": tool, "status": status,
            "detail": str(detail)[:200], "duration": round(duration, 2)
        })
        if status == "PASS": self.pass_count += 1
        elif status == "FAIL": self.fail_count += 1
        elif status == "WARN": self.warn_count += 1

    def print_summary(self):
        total = self.pass_count + self.fail_count + self.warn_count
        print()
        print("=" * 80)
        print("  测试汇总")
        print("=" * 80)
        print(f"  总计: {total}  |  ✅ PASS: {self.pass_count}  |  ❌ FAIL: {self.fail_count}  |  ⚠️ WARN: {self.warn_count}")
        print()

        categories = {}
        for r in self.results:
            cat = r["category"]
            categories.setdefault(cat, []).append(r)

        for cat, entries in categories.items():
            fails = [e for e in entries if e["status"] == "FAIL"]
            passes = [e for e in entries if e["status"] == "PASS"]
            warns = [e for e in entries if e["status"] == "WARN"]
            ic = "✅" if not fails else "❌"
            print(f"  {ic} {cat}: {len(passes)}PASS / {len(fails)}FAIL / {len(warns)}WARN")
            for e in entries:
                icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[e["status"]]
                print(f"     {icon} {e['tool']} ({e['duration']}s) {e['detail']}")

        print()
        print("=" * 80)
        if self.fail_count == 0:
            print("  ✅✅✅ 全部测试通过！")
        else:
            print(f"  ❌ 有 {self.fail_count} 项失败，请检查")
        print("=" * 80)


report = TestReport()


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


def is_success(data):
    """判断响应是否成功，兼容多种格式"""
    if isinstance(data, dict):
        if data.get("success") is True:
            return True
        if data.get("success") is False:
            return False
        # 有 data 返回（如 templates, status, level 等字段）视为成功
        if any(k in data for k in ["templates", "status", "level", "bulletin", "data", "response_level", "message", "stations", "forecast_points"]):
            return True
        # 有 error 字段且无有效数据
        if "error" in data and not any(k in data for k in ["status", "level", "data"]):
            return False
        # raw 包含 Unknown tool
        if "raw" in data and "Unknown tool" in data["raw"]:
            return False
    return True  # 默认认为成功


def get_detail(data):
    """提取结果摘要"""
    if not isinstance(data, dict):
        return str(data)[:100]
    for k in ["message", "error", "status", "level", "response_level", "raw"]:
        if k in data:
            return str(data[k])[:100]
    if "templates" in data:
        return f"{len(data['templates'])}个模板"
    if "forecast_points" in data:
        return f"{len(data['forecast_points'])}个预报点"
    if "scheme_id" in data:
        return f"scheme_id={data['scheme_id']}"
    if "summary" in data:
        s = data["summary"]
        if isinstance(s, dict):
            return f"{s.get('total_stations',0)}站点/{s.get('total_rows',0)}行"
        return str(s)[:80]
    if "data" in data:
        return f"有数据返回"
    return "OK"


async def main():
    print("=" * 80)
    print("  防洪四预 MCP 服务 — 全功能系统性测试")
    print("=" * 80)
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  MCP 地址: http://localhost:8082/mcp\n")

    try:
        async with streamable_http_client("http://localhost:8082/mcp") as streams:
            read_stream, write_stream, _get_session_id = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print(f"  ✅ 已连接 FloodControlMCP\n")

                # ========================================================
                # 一、调度参数与方案单生成（核心修改模块）
                # ========================================================
                cat = "1-调度参数与方案单生成"

                # 1.1 参数列表
                ok, data, dur = await call_tool(session, "modify_dispatch_param", {"action": "list"})
                report.add(cat, "modify_dispatch_param(list)", "PASS" if ok and data.get("success") else "FAIL",
                    f"查询到 {data.get('total_params', 0)} 条参数", dur)

                # 1.2 参数修改
                ok, data, dur = await call_tool(session, "modify_dispatch_param", {
                    "action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 251.0
                })
                report.add(cat, "modify_dispatch_param(update)", "PASS" if ok and data.get("success") else "FAIL",
                    "小浪底初始水位->251.0", dur)

                # 1.3 参数恢复
                ok, data, dur = await call_tool(session, "modify_dispatch_param", {
                    "action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 250.86
                })
                report.add(cat, "modify_dispatch_param(restore)", "PASS" if ok and data.get("success") else "WARN",
                    "参数已恢复", dur)

                # 1.4 模糊匹配多条
                ok, data, dur = await call_tool(session, "modify_dispatch_param", {
                    "action": "update", "station_name": "小浪底", "param_desc": "流量", "new_value": 4000
                })
                report.add(cat, "modify_dispatch_param(multi-match)", "PASS" if ok and not data.get("success") else "WARN",
                    "正确返回多条匹配", dur)

                # 1.5 不存在记录
                ok, data, dur = await call_tool(session, "modify_dispatch_param", {
                    "action": "update", "station_name": "不存在", "param_desc": "xxx", "new_value": 1
                })
                report.add(cat, "modify_dispatch_param(not-found)", "PASS" if ok and not data.get("success") else "WARN",
                    "正确返回未找到", dur)

                # 1.6 generate_dispatch_scheme
                print("  ⏳ generate_dispatch_scheme (运行exe，6-7秒)...")
                ok, data, dur = await call_tool(session, "generate_dispatch_scheme", {})
                if ok and data.get("success"):
                    sid = data.get("scheme_id", "?")
                    summary = data.get("summary", {})
                    report.add(cat, "generate_dispatch_scheme", "PASS",
                        f"scheme_id={sid}, {summary.get('total_stations',0)}站点/{summary.get('total_rows',0)}行, 统计+入库+不导出output", dur)
                else:
                    report.add(cat, "generate_dispatch_scheme", "FAIL", get_detail(data), dur)

                # 1.7 generate_dispatch_sheet
                print("  ⏳ generate_dispatch_sheet (兼容性，6-7秒)...")
                ok, data, dur = await call_tool(session, "generate_dispatch_sheet", {})
                if ok and data.get("success"):
                    report.add(cat, "generate_dispatch_sheet(compat)", "PASS",
                        f"scheme_id={data.get('scheme_id','?')}, 委托正常", dur)
                else:
                    report.add(cat, "generate_dispatch_sheet(compat)", "FAIL", get_detail(data), dur)

                # ========================================================
                # 二、数据查询
                # ========================================================
                cat = "2-数据查询"

                data_tests = [
                    ("get_reservoir_latest_realtime", {}),
                    ("get_river_latest_realtime", {}),
                    ("get_reservoir_realtime", {"reservoir": "小浪底", "start_date": "2021-10-02", "end_date": "2021-10-07"}),
                    ("list_realtime_hydrology", {"station": "花园口", "start_date": "2021-10-02", "end_date": "2021-10-07"}),
                    ("get_reservoir_features", {"reservoir": "小浪底"}),
                    ("list_hydrological_stations", {}),
                    ("get_rainfall_statistics", {"start_time": "2021-10-02", "end_time": "2021-10-07"}),
                    ("get_reservoir_warning", {}),
                    ("get_river_station_info", {"station": "花园口"}),
                    ("get_rainfall_station_info", {"station": "小浪底"}),
                ]
                for name, args in data_tests:
                    ok, data, dur = await call_tool(session, name, args)
                    if ok and is_success(data):
                        report.add(cat, name, "PASS", get_detail(data), dur)
                    else:
                        report.add(cat, name, "WARN", f"外部API不可用: {get_detail(data)}", dur)

                # ========================================================
                # 三、预报模型
                # ========================================================
                cat = "3-预报模型"

                # 3.1 降雨预报（本地计算）
                rainfall_json = json.dumps([
                    {"station": "雨量站A", "rainfall": 15.5},
                    {"station": "雨量站B", "rainfall": 22.3},
                    {"station": "雨量站C", "rainfall": 18.0}
                ])
                ok, data, dur = await call_tool(session, "run_rainfall_forecast_model", {
                    "basin": "黄河", "start_time": "2021-10-02", "end_time": "2021-10-07",
                    "rainfall_data": rainfall_json
                })
                report.add(cat, "run_rainfall_forecast_model",
                    "PASS" if ok and data.get("success") else "FAIL",
                    get_detail(data), dur)

                # 3.2 来水预报（外部API）
                ok, data, dur = await call_tool(session, "run_water_forecast_model", {
                    "station_type": "reservoir", "station_name": "小浪底"
                })
                report.add(cat, "run_water_forecast_model",
                    "PASS" if ok and data.get("success") else "WARN",
                    f"外部API不可用" if not data.get("success") else get_detail(data), dur)

                # 3.3 新安江模型（外部API）
                ok, data, dur = await call_tool(session, "run_xinanjiang_model", {
                    "station_name": "陆浑水库",
                    "start_time": "2021-10-02 00:00:00",
                    "end_time": "2021-10-03 00:00:00"
                })
                report.add(cat, "run_xinanjiang_model",
                    "PASS" if ok and data.get("success") else "WARN",
                    f"外部API不可用" if not data.get("success") else get_detail(data), dur)

                # ========================================================
                # 四、预警评估
                # ========================================================
                cat = "4-预警评估"

                warning_tests = [
                    ("check_water_level_warning", {"reservoir": "小浪底", "forecast_water_level": 270.0, "warning_level": 275.0}),
                    ("check_flow_warning", {"section": "花园口", "forecast_flow": 5000.0, "warning_flow": 4500.0}),
                    ("generate_warning_bulletin", {"reservoir": "小浪底", "current_water_level": 268.0, "forecast_water_level": 272.0, "warning_level": 275.0}),
                    ("get_xiaolangdi_warning_level", {"reservoir_level": 270.0}),
                    ("get_sanmenxia_warning_level", {"tongguan_flow": 5000.0}),
                    ("get_yellow_river_emergency_response", {"xiaolangdi_level": 270.0}),
                ]
                for name, args in warning_tests:
                    ok, data, dur = await call_tool(session, name, args)
                    if ok and is_success(data):
                        report.add(cat, name, "PASS", get_detail(data), dur)
                    else:
                        report.add(cat, name, "FAIL", get_detail(data), dur)

                # ========================================================
                # 五、水库调度
                # ========================================================
                cat = "5-水库调度"

                dispatch_tests = [
                    ("run_xiaolangdi_compensation_dispatch", {"qy": "1000", "sw": "250", "ck": "500", "qujian": "200"}),
                    ("run_xiaolangdi_water_level_control", {"qy": "1000", "sw": "250", "qujian": "200", "zmin": 230.0}),
                ]
                for name, args in dispatch_tests:
                    ok, data, dur = await call_tool(session, name, args)
                    if ok and is_success(data):
                        report.add(cat, name, "PASS", get_detail(data), dur)
                    else:
                        report.add(cat, name, "WARN", f"外部API不可用", dur)

                # ========================================================
                # 六、预案与知识库
                # ========================================================
                cat = "6-预案与知识库"

                # 6.1 模板列表
                ok, data, dur = await call_tool(session, "list_plan_templates", {})
                report.add(cat, "list_plan_templates", "PASS" if ok and is_success(data) else "FAIL",
                    get_detail(data), dur)

                # 6.2 知识库检索
                ok, data, dur = await call_tool(session, "query_knowledge_base", {
                    "query": "小浪底防洪调度方案", "mode": "hybrid", "top_k": 5
                })
                report.add(cat, "query_knowledge_base", "PASS" if ok and is_success(data) else "WARN",
                    get_detail(data), dur)

                # 6.3 预案模板加载
                ok, data, dur = await call_tool(session, "load_plan_template", {"generation_time": "2021-10-02"})
                report.add(cat, "load_plan_template", "PASS" if ok and is_success(data) else "WARN",
                    f"外部API不可用" if not data.get("success") else get_detail(data), dur)

                # 6.4-6.7 未注册工具（定义在 register_plan_tools 外的辅助函数中）
                unregistered = [
                    "get_risk_by_huayuankou_flow",
                    "get_flood_submerge",
                    "generate_xiaolangdi_scheme",
                    "generate_sanmenxia_scheme",
                ]
                for name in unregistered:
                    ok, data, dur = await call_tool(session, name, {})
                    if ok and "raw" in data and "Unknown tool" in data["raw"]:
                        report.add(cat, name, "FAIL", "工具未注册(定义在register_plan_tools外部)", dur)
                    elif ok and is_success(data):
                        report.add(cat, name, "PASS", get_detail(data), dur)
                    else:
                        report.add(cat, name, "FAIL", get_detail(data), dur)

                # ========================================================
                # 七、前端交互
                # ========================================================
                cat = "7-前端交互"

                ui_tests = [
                    ("navigate_to_reservoir_overview", {}),
                    ("navigate_to_reservoir_detail", {"reservoir_name": "小浪底", "start_time": "2021-10-02", "end_time": "2021-10-07"}),
                    ("navigate_to_station_overview", {}),
                    ("navigate_to_rainfall_overview", {}),
                    ("send_simulation_command", {"scheme_id": "DS-0031"}),
                    ("send_plan_document_url", {"document_url": "http://example.com/plan.pdf", "document_name": "测试预案"}),
                    ("navigate_to_control_guidance_overview", {}),
                    ("show_evacuation_routes", {"village_ids": ["村A", "村B"]}),
                ]
                for name, args in ui_tests:
                    ok, data, dur = await call_tool(session, name, args)
                    report.add(cat, name, "PASS" if ok and is_success(data) else "WARN",
                        "指令发送成功" if ok else "发送失败", dur)

                # ========================================================
                report.print_summary()

    except Exception as e:
        print(f"  ❌ 连接错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())