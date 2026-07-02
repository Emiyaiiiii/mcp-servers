#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes 端调用防洪四预 MCP 服务 - 生成调度方案单测试
使用 HTTP + SSE 方式调用（与 Hermes Agent 调用 MCP 方式一致）
"""
import sys
import json
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

MCP_URL = "http://localhost:8082/mcp"


def mcp_sse_call(method, params=None, req_id=1, timeout=300):
    """调用 MCP JSON-RPC over SSE，返回解析后的 result"""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {}
    }).encode('utf-8')

    req = urllib.request.Request(
        MCP_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8')
        for line in body.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                data_str = line[5:].strip()
                if data_str:
                    results.append(json.loads(data_str))
        return results
    except Exception as e:
        return [{"error": str(e)}]


def extract_result(responses):
    """从 SSE 响应列表中提取 result"""
    for r in responses:
        if 'result' in r:
            return r['result']
    return None


def main():
    print("=" * 70)
    print("  Hermes 端 MCP 调用测试 - 生成调度方案单")
    print("=" * 70)
    print(f"  MCP 服务地址: {MCP_URL}")
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ─── 1. Initialize ───────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  步骤 1: MCP 初始化 (initialize)")
    print("=" * 70)
    resp = mcp_sse_call("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "hermes-test", "version": "1.0"}
    }, req_id=1)
    init_result = extract_result(resp)
    if init_result and 'serverInfo' in init_result:
        print(f"  ✅ 服务名: {init_result['serverInfo']['name']}")
        print(f"  ✅ 版本:   {init_result['serverInfo']['version']}")
        print(f"  ✅ 协议:   {init_result['protocolVersion']}")
    else:
        print(f"  ❌ 初始化失败")
        print(f"  响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:500]}")
        return

    # 发送 initialized 通知
    mcp_sse_call("notifications/initialized", {}, req_id=None)

    # ─── 2. 获取工具列表 ─────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  步骤 2: 获取工具列表 (tools/list)")
    print("=" * 70)
    resp = mcp_sse_call("tools/list", {}, req_id=2)
    tools_result = extract_result(resp)
    if tools_result and 'tools' in tools_result:
        tools = tools_result['tools']
        print(f"  ✅ 共发现 {len(tools)} 个工具")
        # 查找目标工具
        target_tools = [t for t in tools if t['name'] in ['generate_dispatch_sheet', 'modify_dispatch_param']]
        for t in target_tools:
            print(f"  → {t['name']}: {t.get('description', '')[:80]}")
    else:
        print(f"  ❌ 获取工具列表失败")
        return

    # ─── 3. 调用 generate_dispatch_sheet ────────────────────────────
    print()
    print("=" * 70)
    print("  步骤 3: 调用 generate_dispatch_sheet 生成调度方案单")
    print("=" * 70)
    print("  （注意：三个表已预先清空，验证数据是新导入的）")

    start_time = time.time()
    resp = mcp_sse_call("tools/call", {
        "name": "generate_dispatch_sheet",
        "arguments": {}
    }, req_id=3, timeout=300)
    elapsed = round(time.time() - start_time, 2)

    call_result = extract_result(resp)
    if call_result and 'content' in call_result:
        content = call_result['content']
        if content:
            text = content[0].get('text', '')
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
        print(f"  ❌ 调用失败")
        print(f"  原始响应: {json.dumps(resp, ensure_ascii=False, indent=2)[:800]}")

    # ─── 4. 验证数据库表数据 ─────────────────────────────────────────
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

    # ─── 总结 ────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  测试总结")
    print("=" * 70)
    print(f"  MCP 服务: {MCP_URL}")
    print(f"  调用方式: HTTP + SSE（与 Hermes Agent 一致）")
    print(f"  总耗时: {elapsed}s")
    print("=" * 70)


if __name__ == "__main__":
    main()