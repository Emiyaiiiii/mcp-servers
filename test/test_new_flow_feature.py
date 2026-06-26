"""新增功能系统性测试
测试项:
1. set_flow_constraint
2. generate_dispatch_scheme 中的 reservoir_stats / reservoir_table
3. apply_parameter_template 联动
"""
import sys
import json
import time
import asyncio
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

sys.stdout.reconfigure(encoding='utf-8')

MCP_URL = "http://localhost:8082/mcp"


class TestReport:
    def __init__(self):
        self.results = []
        self.pass_count = 0
        self.fail_count = 0

    def add(self, category, tool, status, detail="", duration=0):
        self.results.append({
            "category": category, "tool": tool, "status": status,
            "detail": str(detail)[:200], "duration": round(duration, 2)
        })
        if status == "PASS":
            self.pass_count += 1
        else:
            self.fail_count += 1

    def print_summary(self):
        total = self.pass_count + self.fail_count
        print()
        print("=" * 70)
        print(f"  Total: {total}  |  PASS: {self.pass_count}  |  FAIL: {self.fail_count}")
        print(f"  Pass Rate: {self.pass_count/total*100:.1f}%")
        print("=" * 70)

        if self.fail_count > 0:
            print("\nFailed tests:")
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"  - [{r['category']}] {r['tool']}: {r['detail']}")


async def call_tool(session, name, arguments=None):
    """Call MCP tool and return parsed JSON result (text content only)"""
    if arguments is None:
        arguments = {}
    result = await session.call_tool(name, arguments)
    text_content = "".join(c.text for c in result.content)
    try:
        return json.loads(text_content)
    except json.JSONDecodeError:
        return text_content


async def main():
    report = TestReport()

    async with streamable_http_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # ============================================================
            # Setup: apply 下大洪水模板 to ensure 5 reservoirs in Z_Output
            # ============================================================
            list_result = await call_tool(session, "list_parameter_templates", {})
            setup_key = None
            if isinstance(list_result, dict) and list_result.get("templates"):
                for t in list_result["templates"]:
                    if "下大" in t.get("unique_key", "") or "常规" in t.get("name", ""):
                        setup_key = t["unique_key"]
                        break
            if setup_key:
                await call_tool(session, "apply_parameter_template", {
                    "template_name": setup_key,
                    "generate_scheme": True
                })

            # ============================================================
            # Category 1: reservoir stats in generate_dispatch_scheme
            # ============================================================
            cat = "reservoir_stats"

            t0 = time.time()
            result = await call_tool(session, "generate_dispatch_scheme", {})
            dt = time.time() - t0

            # Test 1.1: Scheme generation success
            ok = isinstance(result, dict) and result.get("success")
            report.add(cat, "1.1 scheme generation",
                       "PASS" if ok else "FAIL",
                       f"scheme_id={result.get('scheme_id', 'N/A')}", dt)

            rs_all_5 = False
            if isinstance(result, dict) and result.get("success"):
                summary = result.get("summary", {})
                rs = summary.get("reservoir_stats", [])
                rt = summary.get("reservoir_table", [])
                rs_all_5 = len(rs) >= 5

                # Test 1.2: reservoir_stats exists with data
                ok = len(rs) >= 5
                report.add(cat, "1.2 reservoir_stats has data (5 reservoirs)",
                           "PASS" if ok else "FAIL", f"{len(rs)} reservoirs", 0)

                # Test 1.3: All required fields present
                required = ["reservoir", "max_inflow", "max_outflow", "flood_retention",
                            "max_water_level", "corresponding_storage"]
                all_ok = all(all(f in r for f in required) for r in rs)
                report.add(cat, "1.3 fields complete",
                           "PASS" if (all_ok and len(rs) > 0) else "FAIL",
                           f"{len(required)} fields each", 0)

                # Test 1.4: reservoir_table has correct format
                required_t = ["name", "project", "value"]
                all_ok_t = all(all(f in r for f in required_t) for r in rt)
                res_count = len([r for r in rt if r["name"]])
                ok = all_ok_t and res_count >= 5 and len(rt) >= 25
                report.add(cat, "1.4 reservoir_table format",
                           "PASS" if ok else "FAIL",
                           f"{res_count} reservoirs, {len(rt)} rows", 0)

                # Test 1.5: Data consistency between stats and table
                table_values = []
                for i in range(0, len(rt), 5):
                    if i + 4 < len(rt):
                        table_values.append({
                            "max_inflow": rt[i]["value"],
                            "max_outflow": rt[i+1]["value"],
                            "flood_retention": rt[i+2]["value"],
                            "max_water_level": rt[i+3]["value"],
                            "corresponding_storage": rt[i+4]["value"],
                        })
                match = 0
                for i, s in enumerate(rs):
                    if i >= len(table_values):
                        break
                    tv = table_values[i]
                    if all(abs(tv.get(k, -1) - s[k]) < 0.01 for k in required[1:]):
                        match += 1
                ok = match == len(rs) and len(rs) > 0
                report.add(cat, "1.5 stats == table consistency",
                           "PASS" if ok else "FAIL",
                           f"{match}/{len(rs)} match", 0)

                # Test 1.6: Reasonable value ranges
                reasonable = True
                issues = []
                for r in rs:
                    if not (0 < r["max_inflow"] < 50000):
                        reasonable = False
                        issues.append(f"{r['reservoir']} inflow")
                    if not (0 < r["max_outflow"] < 50000):
                        reasonable = False
                        issues.append(f"{r['reservoir']} outflow")
                    if not (100 < r["max_water_level"] < 600):
                        reasonable = False
                        issues.append(f"{r['reservoir']} water_level")
                report.add(cat, "1.6 value ranges reasonable",
                           "PASS" if (reasonable and len(rs) > 0) else "FAIL",
                           ", ".join(issues) if issues else "all ok", 0)
            else:
                for tn in ["1.2 reservoir_stats has data (5 reservoirs)", "1.3 fields complete",
                           "1.4 reservoir_table format", "1.5 stats == table consistency",
                           "1.6 value ranges reasonable"]:
                    report.add(cat, tn, "FAIL", "scheme generation failed", 0)

            # ============================================================
            # Category 2: set_flow_constraint
            # ============================================================
            cat = "flow_constraint"

            # Test 2.1: Set constraint
            t0 = time.time()
            result = await call_tool(session, "set_flow_constraint",
                                     {"station_name": "花园口", "max_flow": 13000})
            dt = time.time() - t0
            ok = isinstance(result, dict) and result.get("success") and result.get("updated_count", 0) >= 0
            report.add(cat, "2.1 set constraint (13000)",
                       "PASS" if ok else "FAIL",
                       f"updated {result.get('updated_count', 0)} params", dt)

            # Test 2.2: Idempotent (same params = no change)
            t0 = time.time()
            result = await call_tool(session, "set_flow_constraint",
                                     {"station_name": "花园口", "max_flow": 13000})
            dt = time.time() - t0
            ok = isinstance(result, dict) and result.get("success") and result.get("updated_count") == 0
            report.add(cat, "2.2 idempotent call",
                       "PASS" if ok else "FAIL",
                       f"updated_count={result.get('updated_count', 'N/A')}", dt)

            # Test 2.3: Unsupported station
            t0 = time.time()
            result = await call_tool(session, "set_flow_constraint",
                                     {"station_name": "三皇庙", "max_flow": 5000})
            dt = time.time() - t0
            ok = isinstance(result, dict) and result.get("success") is False and result.get("error")
            report.add(cat, "2.3 unsupported station",
                       "PASS" if ok else "FAIL",
                       f"error present: {bool(result.get('error'))}", dt)

            # Test 2.4: Lower target
            t0 = time.time()
            result = await call_tool(session, "set_flow_constraint",
                                     {"station_name": "花园口", "max_flow": 10000})
            dt = time.time() - t0
            ok = isinstance(result, dict) and result.get("success") and result.get("updated_count", 0) >= 4
            report.add(cat, "2.4 lower target (10000)",
                       "PASS" if ok else "FAIL",
                       f"updated {result.get('updated_count', 0)} params", dt)

            # Test 2.5: Verify adjust_type calculation
            if isinstance(result, dict) and result.get("updated_params"):
                params = result["updated_params"]
                target_ok = all(p["new_value"] == 10000 for p in params if p["adjust_type"] == "target")
                buffer_ok = all(p["new_value"] == 9000 for p in params if p["adjust_type"] == "buffer")
                ok = target_ok and buffer_ok
                detail = (f"target={len([p for p in params if p['adjust_type']=='target'])}, "
                          f"buffer={len([p for p in params if p['adjust_type']=='buffer'])}")
            else:
                ok = False
                detail = "no data"
            report.add(cat, "2.5 adjust_type correct",
                       "PASS" if ok else "FAIL", detail, 0)

            # Reset to 13000
            await call_tool(session, "set_flow_constraint",
                            {"station_name": "花园口", "max_flow": 13000})

            # ============================================================
            # Category 3: apply_parameter_template integration
            # ============================================================
            cat = "template_integration"

            # Test 3.1: list templates
            t0 = time.time()
            result = await call_tool(session, "list_parameter_templates", {})
            dt = time.time() - t0
            ok = isinstance(result, dict) and result.get("success") and result.get("count", 0) >= 5
            report.add(cat, "3.1 list templates",
                       "PASS" if ok else "FAIL",
                       f"{result.get('count', 0)} templates", dt)

            # Test 3.2: apply template and verify reservoir_stats in result
            if isinstance(result, dict) and result.get("templates"):
                first_key = result["templates"][0]["unique_key"]
                t0 = time.time()
                apply_result = await call_tool(session, "apply_parameter_template", {
                    "template_name": first_key,
                    "generate_scheme": True
                })
                dt = time.time() - t0
                if isinstance(apply_result, dict) and apply_result.get("success"):
                    rs = apply_result.get("summary", {}).get("reservoir_stats", [])
                    ok = len(rs) >= 2  # some schemes only use 2 reservoirs
                    detail = f"{len(rs)} reservoirs in stats"
                else:
                    ok = False
                    detail = apply_result.get("error", "unknown error") if isinstance(apply_result, dict) else "bad result"
                report.add(cat, "3.2 apply template has reservoir_stats",
                           "PASS" if ok else "FAIL", detail, dt)
            else:
                report.add(cat, "3.2 apply template has reservoir_stats",
                           "FAIL", "no templates available", 0)

            # ============================================================
            # Print results by category
            # ============================================================
            current_cat = None
            for r in report.results:
                if r["category"] != current_cat:
                    current_cat = r["category"]
                    print(f"\n--- {current_cat} ---")
                status_icon = "PASS" if r["status"] == "PASS" else "FAIL"
                print(f"  [{status_icon}] {r['tool']} ({r['duration']}s)")
                if r["status"] == "FAIL":
                    print(f"         {r['detail']}")

            report.print_summary()
            return report.pass_count, report.fail_count + report.pass_count


if __name__ == "__main__":
    passed, total = asyncio.run(main())
    sys.exit(0 if passed == total else 1)
