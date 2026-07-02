#!/usr/bin/env python3
"""
防洪四预 MCP 服务 - 分任务测试
任务一：参数修改（modify_dispatch_param）
任务二：调度方案单生成（generate_dispatch_sheet）
"""
import asyncio
import json
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, 'D:/code/mcp-servers/src')
from src.tools.forecast_models import register_forecast_models
from fastmcp import FastMCP


class TaskTestRunner:
    def __init__(self):
        self.mcp = FastMCP('test')
        register_forecast_models(self.mcp)
        self.results = []

    async def call_tool(self, tool_name, params):
        try:
            return await self.mcp.call_tool(tool_name, params)
        except Exception as e:
            return type('obj', (object,), {
                'structured_content': {"success": False, "error": str(e)},
            })()

    async def run_test(self, test_id, description, tool_name, params, expected_type="success"):
        """
        执行单个测试
        expected_type: success / business_error / system_error
        """
        result = {
            "id": test_id,
            "description": description,
            "tool": tool_name,
            "params": params,
            "expected_type": expected_type,
            "status": "pending",
            "duration_ms": None,
            "response_data": None,
        }

        try:
            start = time.time()
            response = await self.call_tool(tool_name, params)
            result["duration_ms"] = round((time.time() - start) * 1000, 2)

            if hasattr(response, 'structured_content'):
                result["response_data"] = response.structured_content

            success = result["response_data"].get("success", False) if result["response_data"] else False

            if expected_type == "success":
                result["status"] = "pass" if success else "fail"
            elif expected_type == "business_error":
                result["status"] = "pass" if not success else "fail"
            else:
                result["status"] = "fail"

        except Exception as e:
            result["status"] = "fail" if expected_type != "system_error" else "pass"
            result["response_data"] = {"error": str(e)}
            result["duration_ms"] = round((time.time() - start) * 1000, 2)

        self.results.append(result)
        return result

    def print_result(self, r):
        status_icon = {"pass": "✅", "fail": "❌", "pending": "⏳"}.get(r["status"], "❓")
        print(f"  {status_icon} [{r['id']}] {r['description']}")
        print(f"     耗时: {r['duration_ms']}ms")
        resp = r.get("response_data")
        if resp:
            if resp.get("success"):
                if "total_params" in resp:
                    print(f"     → total_params: {resp['total_params']}")
                if "message" in resp:
                    print(f"     → {resp['message']}")
                if "before" in resp and "after" in resp:
                    print(f"     → {resp['before']['Control_Par']} → {resp['after']['Control_Par']}")
                if "output_file" in resp:
                    print(f"     → 输出文件: {resp['output_file']}")
                if "steps" in resp:
                    steps = resp["steps"]
                    for name, info in steps.items():
                        rows = info.get("rows", info.get("output_rows", "N/A"))
                        t = info.get("elapsed_seconds", "N/A")
                        print(f"     → {name}: {t}s")
            else:
                print(f"     → 错误: {resp.get('error', 'N/A')}")
                if "available_params" in resp:
                    print(f"     → 提供 {len(resp['available_params'])} 条可用参数")
                if "matches" in resp:
                    print(f"     → 匹配 {len(resp['matches'])} 条记录")

    def print_summary(self, task_name):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = total - passed
        print(f"\n{'='*70}")
        print(f"  {task_name} - 测试摘要")
        print(f"{'='*70}")
        print(f"  总测试: {total}")
        print(f"  通过: {passed} ✅")
        print(f"  失败: {failed} ❌")
        print(f"  通过率: {passed/total*100:.1f}%")
        print(f"{'='*70}")


async def task1_param_modification():
    """任务一：参数修改测试"""
    print("\n" + "="*70)
    print("  任务一：参数修改测试 (modify_dispatch_param)")
    print("="*70)

    runner = TaskTestRunner()

    # 用例 1: 查看所有参数
    await runner.run_test(
        "P01", "查看所有调度参数",
        "modify_dispatch_param",
        {"action": "list"},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 2: 修改敞泄/控泄模式
    await runner.run_test(
        "P02", "修改小浪底为敞泄模式",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "控泄", "new_value": 0},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 3: 修改初始水位
    await runner.run_test(
        "P03", "修改小浪底初始水位为 251.0",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 251.0},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 4: 修改发电流量
    await runner.run_test(
        "P04", "修改小浪底发电流量为 500",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "发电流量", "new_value": 500},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 5: 修改洪水类型
    await runner.run_test(
        "P05", "切换洪水类型为上大洪水",
        "modify_dispatch_param",
        {"action": "update", "station_name": "洪水类型", "param_desc": "上大洪水", "new_value": 0},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 6: 模糊匹配多条（预期业务错误）
    await runner.run_test(
        "P06", "模糊关键词'预泄'匹配多条",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "预泄", "new_value": 1},
        "business_error"
    )
    runner.print_result(runner.results[-1])

    # 用例 7: 站点不存在（预期业务错误）
    await runner.run_test(
        "P07", "修改不存在站点的参数",
        "modify_dispatch_param",
        {"action": "update", "station_name": "不存在的水库", "param_desc": "水位", "new_value": 100},
        "business_error"
    )
    runner.print_result(runner.results[-1])

    # 用例 8: 恢复所有修改的参数
    print("\n  --- 恢复参数 ---")
    await runner.run_test(
        "P02-R", "恢复小浪底控泄模式",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "控泄", "new_value": 1},
        "success"
    )
    runner.print_result(runner.results[-1])

    await runner.run_test(
        "P03-R", "恢复小浪底初始水位",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 250.86},
        "success"
    )
    runner.print_result(runner.results[-1])

    await runner.run_test(
        "P04-R", "恢复小浪底发电流量",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "发电流量", "new_value": 300},
        "success"
    )
    runner.print_result(runner.results[-1])

    await runner.run_test(
        "P05-R", "恢复洪水类型为下大洪水",
        "modify_dispatch_param",
        {"action": "update", "station_name": "洪水类型", "param_desc": "下大洪水", "new_value": 1},
        "success"
    )
    runner.print_result(runner.results[-1])

    runner.print_summary("任务一：参数修改")
    return runner


async def task2_dispatch_sheet():
    """任务二：调度方案单生成测试"""
    print("\n" + "="*70)
    print("  任务二：调度方案单生成测试 (generate_dispatch_sheet)")
    print("="*70)

    runner = TaskTestRunner()

    # 用例 1: 正常生成调度方案单
    await runner.run_test(
        "D01", "正常生成调度方案单",
        "generate_dispatch_sheet",
        {},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 2: 修改参数后重新生成
    print("\n  --- 先修改参数再生成 ---")
    # 修改参数
    await runner.run_test(
        "D02-pre", "修改小浪底初始水位为 252.0",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 252.0},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 重新生成
    await runner.run_test(
        "D02", "修改参数后重新生成调度方案单",
        "generate_dispatch_sheet",
        {},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 用例 3: 再次生成（验证幂等性）
    await runner.run_test(
        "D03", "连续第二次生成调度方案单",
        "generate_dispatch_sheet",
        {},
        "success"
    )
    runner.print_result(runner.results[-1])

    # 恢复参数
    print("\n  --- 恢复参数 ---")
    await runner.run_test(
        "D02-restore", "恢复小浪底初始水位",
        "modify_dispatch_param",
        {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 250.86},
        "success"
    )
    runner.print_result(runner.results[-1])

    runner.print_summary("任务二：调度方案单生成")
    return runner


async def main():
    print("="*70)
    print("  防洪四预 MCP 服务 - 分任务测试")
    print(f"  测试时间: {datetime.now().isoformat()}")
    print("="*70)

    # 任务一
    runner1 = await task1_param_modification()

    # 任务二
    runner2 = await task2_dispatch_sheet()

    # 总体摘要
    all_results = runner1.results + runner2.results
    total = len(all_results)
    passed = sum(1 for r in all_results if r["status"] == "pass")
    failed = total - passed

    print("\n" + "="*70)
    print("  总体测试摘要")
    print("="*70)
    print(f"  总测试数: {total}")
    print(f"  通过: {passed} ✅")
    print(f"  失败: {failed} ❌")
    print(f"  总通过率: {passed/total*100:.1f}%")
    print("="*70)

    # 保存报告
    report = {
        "generated_at": datetime.now().isoformat(),
        "task1_param_modification": {
            "total": len(runner1.results),
            "passed": sum(1 for r in runner1.results if r["status"] == "pass"),
            "results": runner1.results,
        },
        "task2_dispatch_sheet": {
            "total": len(runner2.results),
            "passed": sum(1 for r in runner2.results if r["status"] == "pass"),
            "results": runner2.results,
        },
        "overall": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%",
        }
    }

    report_path = "D:/code/mcp-servers/test/task_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())