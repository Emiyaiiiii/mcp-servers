#!/usr/bin/env python3
"""
防洪四预 MCP 服务集成测试脚本
直接调用 MCP 工具进行测试
"""
import asyncio
import json
import sys
import os
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, 'D:/code/mcp-servers/src')
from src.tools.forecast_models import register_forecast_models
from fastmcp import FastMCP


class MCPTestRunner:
    """MCP 工具测试运行器"""

    def __init__(self):
        self.mcp = FastMCP('test')
        register_forecast_models(self.mcp)
        self.results = []

    async def call_tool(self, tool_name, params):
        """调用 MCP 工具"""
        try:
            return await self.mcp.call_tool(tool_name, params)
        except Exception as e:
            return type('obj', (object,), {
                'structured_content': {"success": False, "error": str(e)},
                'content': [type('obj', (object,), {'text': json.dumps({"error": str(e)})})()]
            })()

    async def run_test(self, test_case):
        """执行单个测试"""
        test_id = test_case["id"]
        tool_name = test_case["tool"]
        params = test_case["params"]
        description = test_case["description"]
        expected = test_case["expected"]

        result = {
            "id": test_id,
            "description": description,
            "tool": tool_name,
            "expected": expected,
            "status": "pending",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "duration_ms": None,
            "request": params,
            "response": None,
            "response_data": None,
            "error": None,
        }

        try:
            start = time.time()
            response = await self.call_tool(tool_name, params)
            result["duration_ms"] = round((time.time() - start) * 1000, 2)
            result["end_time"] = datetime.now().isoformat()

            # 解析响应
            if hasattr(response, 'structured_content'):
                result["response_data"] = response.structured_content
            elif hasattr(response, 'content') and response.content:
                text = response.content[0].text
                try:
                    result["response_data"] = json.loads(text)
                except:
                    result["response_data"] = {"raw": text}

            result["response"] = str(result["response_data"])[:200]
            result["status"] = "success"

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["end_time"] = datetime.now().isoformat()
            result["duration_ms"] = round((time.time() - start) * 1000, 2)

        return result

    async def run_all_tests(self, test_cases):
        """执行所有测试"""
        for test in test_cases:
            print(f"\n[{test['id']}] {test['description']}")
            print(f"  工具: {test['tool']}")
            print(f"  参数: {json.dumps(test['params'], ensure_ascii=False)}")

            result = await self.run_test(test)
            self.results.append(result)

            if result["status"] == "success":
                resp = result["response_data"]
                success = resp.get("success", False) if isinstance(resp, dict) else False

                if success:
                    print(f"  ✅ 成功 ({result['duration_ms']}ms)")
                    if "total_params" in resp:
                        print(f"     → total_params: {resp['total_params']}")
                    if "message" in resp:
                        print(f"     → message: {resp['message']}")
                    if "before" in resp and "after" in resp:
                        print(f"     → {resp['before']['Control_Par']} → {resp['after']['Control_Par']}")
                    if "output_file" in resp:
                        print(f"     → output_file: {resp['output_file']}")
                    if "steps" in resp:
                        print(f"     → steps: {list(resp['steps'].keys())}")
                else:
                    print(f"  ⚠️ 业务错误 ({result['duration_ms']}ms)")
                    print(f"     → error: {resp.get('error', 'N/A')}")
                    if "available_params" in resp:
                        print(f"     → 提供 {len(resp['available_params'])} 条可用参数")
                    if "matches" in resp:
                        print(f"     → 匹配 {len(resp['matches'])} 条记录")
            else:
                print(f"  ❌ 失败: {result['error']}")

        return self.results

    def generate_report(self):
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "success" and r["response_data"].get("success", False))
        business_failed = sum(1 for r in self.results if r["status"] == "success" and not r["response_data"].get("success", True))
        failed = sum(1 for r in self.results if r["status"] == "failed")

        return {
            "test_summary": {
                "total": total,
                "passed": passed,
                "business_failed": business_failed,
                "failed": failed,
                "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "0%",
                "start_time": self.results[0]["start_time"] if self.results else None,
                "end_time": self.results[-1]["end_time"] if self.results else None,
            },
            "test_results": self.results,
        }


# 测试用例
TEST_CASES = [
    # 一、modify_dispatch_param 测试
    {
        "id": "Q01",
        "tool": "modify_dispatch_param",
        "description": "查看当前调度参数",
        "params": {"action": "list"},
        "expected": "返回全部 46 条参数记录"
    },
    {
        "id": "Q04",
        "tool": "modify_dispatch_param",
        "description": "把小浪底改为敞泄模式",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "控泄", "new_value": 0},
        "expected": "更新 Control_Par=0"
    },
    {
        "id": "Q04-R",
        "tool": "modify_dispatch_param",
        "description": "恢复小浪底控泄设置",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "控泄", "new_value": 1},
        "expected": "恢复 Control_Par=1"
    },
    {
        "id": "Q05",
        "tool": "modify_dispatch_param",
        "description": "将小浪底初始水位改成 250.5",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 250.5},
        "expected": "更新 Control_Par=250.5"
    },
    {
        "id": "Q05-R",
        "tool": "modify_dispatch_param",
        "description": "恢复小浪底初始水位",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 250.86},
        "expected": "恢复 Control_Par=250.86"
    },
    {
        "id": "Q09",
        "tool": "modify_dispatch_param",
        "description": "将洪水类型切换为上大洪水",
        "params": {"action": "update", "station_name": "洪水类型", "param_desc": "上大洪水", "new_value": 0},
        "expected": "更新 Control_Par=0"
    },
    {
        "id": "Q09-R",
        "tool": "modify_dispatch_param",
        "description": "恢复洪水类型为下大洪水",
        "params": {"action": "update", "station_name": "洪水类型", "param_desc": "下大洪水", "new_value": 1},
        "expected": "恢复 Control_Par=1"
    },
    {
        "id": "Q11",
        "tool": "modify_dispatch_param",
        "description": "修改不存在的站点参数",
        "params": {"action": "update", "station_name": "不存在的站点", "param_desc": "水位", "new_value": 100},
        "expected": "返回错误，提示站点不存在"
    },
    {
        "id": "Q12",
        "tool": "modify_dispatch_param",
        "description": "用模糊关键词修改",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "泄", "new_value": 0},
        "expected": "返回多条匹配项"
    },
    {
        "id": "Q13",
        "tool": "modify_dispatch_param",
        "description": "参数验证 - 缺少 new_value",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "控泄", "new_value": None},
        "expected": "返回参数验证错误"
    },
    # 二、generate_dispatch_sheet 测试
    {
        "id": "Q17",
        "tool": "generate_dispatch_sheet",
        "description": "生成调度方案单",
        "params": {},
        "expected": "执行完整流程并生成输出文件"
    },
]


async def main():
    """主函数"""
    print("=" * 70)
    print("防洪四预 MCP 服务集成测试报告")
    print("=" * 70)
    print(f"测试时间: {datetime.now().isoformat()}")
    print(f"项目路径: D:\\code\\mcp-servers")
    print("=" * 70)

    runner = MCPTestRunner()
    await runner.run_all_tests(TEST_CASES)

    # 生成报告
    report = runner.generate_report()

    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    summary = report["test_summary"]
    print(f"总测试数: {summary['total']}")
    print(f"通过: {summary['passed']} ✅")
    print(f"业务失败: {summary['business_failed']} ⚠️")
    print(f"系统错误: {summary['failed']} ❌")
    print(f"通过率: {summary['pass_rate']}")

    # 保存报告
    report_path = "D:/code/mcp-servers/test/mcp_integration_test_report.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")

    # 生成 Markdown 报告
    md_report = f"""# 防洪四预 MCP 服务测试报告

## 测试摘要

| 指标 | 值 |
|------|-----|
| 测试时间 | {summary['start_time']} ~ {summary['end_time']} |
| 总测试数 | {summary['total']} |
| 通过 | {summary['passed']} ✅ |
| 业务失败 | {summary['business_failed']} ⚠️ |
| 系统错误 | {summary['failed']} ❌ |
| 通过率 | {summary['pass_rate']} |

## 测试结果详情

| 编号 | 测试描述 | 工具 | 状态 | 耗时 |
|------|----------|------|------|------|
"""
    for r in report["test_results"]:
        status_icon = "✅" if r["status"] == "success" and r["response_data"].get("success", False) else ("⚠️" if r["status"] == "success" else "❌")
        resp_preview = ""
        if r.get("response_data"):
            if isinstance(r["response_data"], dict):
                if "message" in r["response_data"]:
                    resp_preview = r["response_data"]["message"]
                elif "error" in r["response_data"]:
                    resp_preview = r["response_data"]["error"]
                elif "output_file" in r["response_data"]:
                    resp_preview = r["response_data"]["output_file"]
        md_report += f"| {r['id']} | {r['description']} | {r['tool']} | {status_icon} | {r['duration_ms']}ms |\n"

    md_report += """
## 工具说明

### modify_dispatch_param
- **功能**: 查看或修改 `data.mdb` 中 `Dispatch_Par` 表的调度参数
- **参数**:
  - `action`: 操作类型 ("list" 或 "update")
  - `station_name`: 站点名称
  - `param_desc`: 参数说明关键词
  - `new_value`: 新的参数值

### generate_dispatch_sheet
- **功能**: 一键生成调度方案单
- **流程**: 导入 Excel → 运行 RegualDispacth.exe → 导出结果
- **输出**: `output/Q_Output_YYYYMMDD_HHMMSS.xlsx`
"""
    md_path = "D:/code/mcp-servers/test/mcp_test_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"Markdown 报告已保存: {md_path}")

    return report


if __name__ == "__main__":
    asyncio.run(main())