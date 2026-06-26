#!/usr/bin/env python3
"""
防洪四预 MCP 服务 Hermes Agent 测试脚本
使用 MCP Python SDK 直接调用 MCP 服务
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# MCP 服务配置
MCP_SERVER_CONFIG = {
    "name": "flood-control-mcp",
    "command": "C:\\Users\\遥遥领先\\AppData\\Local\\Python\\pythoncore-3.14-64\\Scripts\\uv.exe",
    "args": ["run", "python", "-c",
             "import sys; sys.path.insert(0, 'D:/code/mcp-servers/src'); "
             "from src.server import run_server; run_server(transport='streamable-http')"],
    "env": {},
}

# 测试问题列表
TEST_QUESTIONS = [
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
        "id": "Q05",
        "tool": "modify_dispatch_param",
        "description": "将小浪底初始水位改成 250.5",
        "params": {"action": "update", "station_name": "小浪底", "param_desc": "初始水位", "new_value": 250.5},
        "expected": "更新 Control_Par=250.5"
    },
    {
        "id": "Q09",
        "tool": "modify_dispatch_param",
        "description": "将洪水类型切换为上大洪水",
        "params": {"action": "update", "station_name": "洪水类型", "param_desc": "上大洪水", "new_value": 0},
        "expected": "更新 Control_Par=0"
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
    # 二、generate_dispatch_sheet 测试
    {
        "id": "Q17",
        "tool": "generate_dispatch_sheet",
        "description": "生成调度方案单",
        "params": {},
        "expected": "执行完整流程并生成输出文件"
    },
]


class MCPTestRunner:
    def __init__(self, server_url="http://localhost:8082/mcp"):
        self.server_url = server_url
        self.results = []
        self.session = None

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
            "error": None,
        }

        try:
            start = time.time()

            if self.session:
                response = await self.session.call_tool(tool_name, params)
                result["response"] = response.content[0].text if response.content else ""
            else:
                # 使用 HTTP 客户端调用
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        self.server_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/call",
                            "params": {
                                "name": tool_name,
                                "arguments": params
                            }
                        },
                        timeout=60.0
                    )
                    result["response"] = resp.text

            result["duration_ms"] = round((time.time() - start) * 1000, 2)
            result["status"] = "success"
            result["end_time"] = datetime.now().isoformat()

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["end_time"] = datetime.now().isoformat()
            result["duration_ms"] = round((time.time() - start) * 1000, 2)

        return result

    async def run_all_tests(self):
        """执行所有测试"""
        print("=" * 70)
        print("防洪四预 MCP 服务测试报告")
        print("=" * 70)
        print(f"测试时间: {datetime.now().isoformat()}")
        print(f"服务器地址: {self.server_url}")
        print("=" * 70)

        for test in TEST_QUESTIONS:
            print(f"\n[{test['id']}] {test['description']}")
            print(f"  工具: {test['tool']}")
            print(f"  参数: {json.dumps(test['params'], ensure_ascii=False)}")

            result = await self.run_test(test)
            self.results.append(result)

            if result["status"] == "success":
                print(f"  ✅ 成功 ({result['duration_ms']}ms)")
                # 解析响应
                try:
                    resp_data = json.loads(result["response"]) if isinstance(result["response"], str) else result["response"]
                    if isinstance(resp_data, dict):
                        success = resp_data.get("success", True)
                        if success:
                            print(f"     → 返回 success: {success}")
                            if "total_params" in resp_data:
                                print(f"     → total_params: {resp_data['total_params']}")
                            if "message" in resp_data:
                                print(f"     → message: {resp_data['message']}")
                            if "output_file" in resp_data:
                                print(f"     → output_file: {resp_data['output_file']}")
                        else:
                            print(f"     → 返回 error: {resp_data.get('error', 'N/A')}")
                except:
                    pass
            else:
                print(f"  ❌ 失败: {result['error']}")

        return self.results

    def generate_report(self):
        """生成测试报告"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "success")
        failed = total - passed

        report = {
            "test_summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "0%",
                "start_time": self.results[0]["start_time"] if self.results else None,
                "end_time": self.results[-1]["end_time"] if self.results else None,
            },
            "test_results": self.results,
        }

        return report


async def main():
    """主函数"""
    print("防洪四预 MCP 服务测试")
    print("=" * 70)

    # 检查服务是否运行
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8082/mcp", timeout=5.0)
            print(f"✅ MCP 服务已启动: {resp.status_code}")
    except Exception as e:
        print(f"❌ MCP 服务未运行: {e}")
        print("请先启动 MCP 服务: python -m uv run python -c \"from src.server import run_server; run_server(transport='streamable-http')\"")
        return

    runner = MCPTestRunner()
    await runner.run_all_tests()

    # 生成报告
    report = runner.generate_report()

    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    print(f"总测试数: {report['test_summary']['total']}")
    print(f"通过: {report['test_summary']['passed']} ✅")
    print(f"失败: {report['test_summary']['failed']} ❌")
    print(f"通过率: {report['test_summary']['pass_rate']}")

    # 保存报告
    report_path = "D:/code/mcp-servers/test/mcp_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")

    return report


if __name__ == "__main__":
    asyncio.run(main())