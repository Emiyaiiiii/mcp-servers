from typing import Dict, Any
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_risk_by_huayuankou_flow_core(flow: float) -> dict:
    """
    根据花园口流量判断黄河出险状况。

    Args:
        flow: 花园口流量，单位 m³/s

    Returns:
        完整出险信息，包含流量等级、河南和山西的风险描述、危险类型和处置建议
    """
    try:
        result = {
            "flow": flow,
            "level": "",
            "henan": "",
            "shanxi": "",
            "danger_type": [],
            "suggestion": ""
        }

        if flow < 4000:
            result["level"] = "4000m³/s 以下"
            result["henan"] = "流量持续较久时，花园口以下宽河道河势可能较大变化，部分河道工程长期受冲可能发生较大及以上险情。"
            result["shanxi"] = "由黄河河务部门查险抢险；河势突变、漫滩或较大险情时，市县领导靠前指挥。"
            result["danger_type"] = ["河势变化", "河道工程受冲险情"]
            result["suggestion"] = "正常巡查防守，关注河势变化。"

        elif 4000 <= flow < 6000:
            result["level"] = "4000～6000m³/s"
            result["henan"] = "部分工程接近或超标准，低滩区可能漫水，河势易上提/下挫、坐湾生险，工程出险几率增大。"
            result["shanxi"] = "冲刷力强，局部河势变化大；险工、控导、新修工程易根石走失、坦石坍塌、墩蛰；部分控导可能漫顶；漫滩偎堤易风浪淘刷、渗水、管涌；道路可能中断。"
            result["danger_type"] = ["低滩漫水", "河势变化", "工程出险", "风浪淘刷", "渗水", "管涌"]
            result["suggestion"] = "重点盯防控导、险工、新修工程，加强巡查。"

        elif 6000 <= flow < 10000:
            result["level"] = "6000～10000m³/s"
            result["henan"] = "部分高滩、全部低滩漫水，水深1~3m；偎堤水深1~4m；涉及6市，人口62.90~198.97万，转移6.77~91.75万人。"
            result["shanxi"] = "临黄大堤大部/全部偎水，堤根水深2~6m；薄弱堤段易渗水、管涌、裂缝、坍塌、顺堤行洪、风浪淘刷；控导大部/全部漫顶，可能揭顶后溃；河口流路可能摆动/分汊；险工易根石走失、坝岸墩蛰。"
            result["danger_type"] = ["滩区漫水", "偎堤", "渗水", "管涌", "坍塌", "控导漫顶", "河势变化", "河口分汊"]
            result["suggestion"] = "全面巡查堤防，重点防守薄弱段、控导工程，做好滩区转移准备。"

        elif 10000 <= flow < 15000:
            result["level"] = "10000～15000m³/s"
            result["henan"] = "滩区大部分被淹；偎堤长度约560km，水深2~5m；涉及6市，人口198.97~209.50万，转移91.75~113.94万人。"
            result["shanxi"] = "工程面临严峻考验；险工易坍塌、墩蛰、垮坝；控导全部漫顶、部分揭顶后溃；河势巨变，可能斜河、横河；多堤段易顺堤行洪；堤防易严重渗水、管涌、滑坡、漏洞、风浪塌坡；河口流路可能摆动/分汊；东平湖围坝可能出险；桥梁、管线易受撞击。"
            result["danger_type"] = ["滩区大部淹没", "偎堤", "渗水", "管涌", "滑坡", "漏洞", "垮坝", "控导溃失", "斜河横河", "顺堤行洪", "河口分汊"]
            result["suggestion"] = "全线设防，人员全部上堤，重点防控漏洞、滑坡、顺堤行洪。"

        elif 15000 <= flow < 22000:
            result["level"] = "15000～22000m³/s"
            result["henan"] = "堤防全线偎水，最大水深8m；滩区全部上水，局部水深超5m；涉及人口209.50~211.13万，转移113.94~120.81万人。"
            result["shanxi"] = "水位高、流速大、持续久；险工普遍坍塌、墩蛰、垮坝；堤防险情剧增，易漏洞；控导严重揭顶后溃；河势巨变；多堤段极易顺堤行洪；流量>18000时东明河段可能滚河；东平湖围堤险情严重；河口可能顺堤行洪、流路摆动/分汊；桥梁设施易撞击损毁。"
            result["danger_type"] = ["全线偎堤", "滩区全淹", "垮坝", "漏洞", "顺堤行洪", "滚河风险", "控导溃失", "河势巨变", "河口分汊"]
            result["suggestion"] = "一级战备，全员上堤，严防滚河、漏洞、顺堤行洪，启用应急抢险预案。"

        elif flow >= 22000:
            result["level"] = "≥22000m³/s（超标准洪水）"
            result["henan"] = "堤防全线偎水，随时可能渗漏、管涌、脱坡等重大险情；滩区全部被淹。"
            result["shanxi"] = "滩区全部漫滩，堤根水深≥8.5m；水位超标准；高村以上利用超高/子堰行洪；高村以下启用北金堤滞洪区；东平湖滞洪，控制艾山以下≤10000m³/s。"
            result["danger_type"] = ["全线重大险情", "漫滩", "偎水", "超标准运用", "滞洪区运用"]
            result["suggestion"] = "启动超标准洪水预案，启用北金堤、东平湖滞洪，全力保堤防安全。"

        return result

    except Exception as e:
        error_msg = f"判断出险情况时出错: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}


def get_flood_submerge_core(huayuankou_flow: float) -> dict:
    """
    黄河滩区淹没分析。

    Args:
        huayuankou_flow: 花园口流量，单位 m³/s

    Returns:
        淹没结果，包含河南、山东的淹没数据、等级和描述
    """
    try:
        q = huayuankou_flow
        result = {
            "flow": q,
            "level": "",
            "description": "",
            "henan": {},
            "shandong": {}
        }

        if q < 6000:
            result["level"] = "<6000 m³/s"
            result["description"] = "主河道正常行洪，不会漫滩，无村庄围困，无需迁移安置"
            result["henan"] = {
                "进水村庄数": 0,
                "进水人口": 0,
                "水围村庄数": 0,
                "水围人口": 0,
                "淹没滩地(万亩)": 0,
                "淹没耕地(万亩)": 0,
                "经济损失(亿元)": 0,
                "备注": "无淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 0,
                "淹没耕地(万亩)": 0,
                "滩区进水数": 0,
                "自然村进水数": 0,
                "自然村围困数": 0,
                "涉及人口": 0,
                "需转移安置": 0,
                "就地就近安置": 0,
                "备注": "无淹没"
            }

        elif 6000 <= q < 8000:
            result["level"] = "6000 m³/s"
            result["description"] = "开始漫滩，河南、山东滩区局部进水、围困"
            result["henan"] = {
                "进水村庄数": 70,
                "进水人口": 6.18,
                "水围村庄数": 273,
                "水围人口": 24.85,
                "淹没滩地(万亩)": 110.29,
                "淹没耕地(万亩)": 70.81,
                "经济损失(亿元)": 140.87,
                "备注": "局部淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 39.07,
                "淹没耕地(万亩)": 31.40,
                "滩区进水数": 93,
                "自然村进水数": 18,
                "自然村围困数": 46,
                "涉及人口": 4.54,
                "需转移安置": 2.46,
                "就地就近安置": 2.09,
                "备注": "局部漫滩"
            }

        elif 8000 <= q < 10000:
            result["level"] = "8000 m³/s"
            result["description"] = "大面积漫滩，河南、山东淹没范围显著扩大"
            result["henan"] = {
                "进水村庄数": 438,
                "进水人口": 51.47,
                "水围村庄数": 280,
                "水围人口": 27.07,
                "淹没滩地(万亩)": 215.53,
                "淹没耕地(万亩)": 152.85,
                "经济损失(亿元)": 327.17,
                "备注": "大面积淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 204.05,
                "淹没耕地(万亩)": 134.34,
                "滩区进水数": 108,
                "自然村进水数": 105,
                "自然村围困数": 206,
                "涉及人口": 25.26,
                "需转移安置": 5.70,
                "就地就近安置": 16.98,
                "备注": "大面积漫滩"
            }

        elif 10000 <= q < 12370:
            result["level"] = "10000 m³/s"
            result["description"] = "山东滩区全部漫滩，河南大规模淹没"
            result["henan"] = {
                "进水村庄数": 905,
                "进水人口": 112.70,
                "水围村庄数": 191,
                "水围人口": 18.53,
                "淹没滩地(万亩)": 323.22,
                "淹没耕地(万亩)": 219.20,
                "经济损失(亿元)": 467.43,
                "备注": "大规模淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 228.35,
                "淹没耕地(万亩)": 174.27,
                "滩区进水数": 109,
                "自然村进水数": 222,
                "自然村围困数": 161,
                "涉及人口": 31.42,
                "需转移安置": 7.44,
                "就地就近安置": 22.63,
                "备注": "全部漫滩"
            }

        elif 12370 <= q < 15700:
            result["level"] = "12370 m³/s"
            result["description"] = "河南接近全淹没，山东维持全漫滩"
            result["henan"] = {
                "进水村庄数": 1029,
                "进水人口": 125.22,
                "水围村庄数": 80,
                "水围人口": 6.97,
                "淹没滩地(万亩)": 329.80,
                "淹没耕地(万亩)": 223.09,
                "经济损失(亿元)": 494.89,
                "备注": "接近全淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩"
            }

        elif 15700 <= q < 22000:
            result["level"] = "15700~22000 m³/s（大洪水）"
            result["description"] = "河南全滩区淹没，山东全漫滩"
            result["henan"] = {
                "进水村庄数": 1103,
                "进水人口": 134.30,
                "水围村庄数": 48,
                "水围人口": 3.99,
                "淹没滩地(万亩)": 342.10,
                "淹没耕地(万亩)": 234.10,
                "经济损失(亿元)": 507.66,
                "备注": "全滩区淹没"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩"
            }

        elif q >= 22000:
            result["level"] = "≥22000 m³/s（超标准洪水）"
            result["description"] = "启用北金堤、东平湖滞洪区，全力保堤防安全"
            result["henan"] = {
                "进水村庄数": 1103,
                "进水人口": 134.30,
                "水围村庄数": 48,
                "水围人口": 3.99,
                "淹没滩地(万亩)": 342.10,
                "淹没耕地(万亩)": 234.10,
                "经济损失(亿元)": 507.66,
                "备注": "全滩区淹没，启用北金堤滞洪区"
            }
            result["shandong"] = {
                "漫滩面积(万亩)": 234.71,
                "淹没耕地(万亩)": 176.90,
                "滩区进水数": 109,
                "自然村进水数": 243,
                "自然村围困数": 157,
                "涉及人口": 31.68,
                "需转移安置": 20.09,
                "就地就近安置": 11.59,
                "备注": "全漫滩，启用东平湖滞洪区"
            }

        return result

    except Exception as e:
        error_msg = f"淹没分析时出错: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}


def calculate_flood_submergence(garden_mouth_peak_flow: float) -> dict:
    """根据花园口洪峰流量，按分段表线性插值计算滩区淹没
    
    分段表数据（河南+山东合并汇总）：
    - 4000: 不漫滩, 涉及人口=0, 转移人口=0, 淹没面积=0
    - 6000: 涉及人口=4.54, 转移人口=2.46, 淹没面积=39.07
    - 8000: 涉及人口=176.69, 转移人口=0, 淹没面积=545.33  (河南两组数据取大值)
    - 10000: 涉及人口=112.70, 转移人口=0, 淹没面积=323.22
    - 12370: 涉及人口=31.42, 转移人口=7.44, 淹没面积=228.35
    - 15700: 涉及人口=159.56, 转移人口=5.70, 淹没面积=546.15
    - 22000: 涉及人口=182.52, 转移人口=20.09, 淹没面积=710.00
    """
    SEGMENTS = [
        (4000, 0, 0, 0),
        (6000, 4.54, 2.46, 39.07),
        (8000, 176.69, 0, 545.33),
        (10000, 112.70, 0, 323.22),
        (12370, 31.42, 7.44, 228.35),
        (15700, 159.56, 5.70, 546.15),
        (22000, 182.52, 20.09, 710.00),
    ]
    
    q = garden_mouth_peak_flow
    
    if q < 4000:
        return {
            "garden_mouth_peak": q,
            "involved_population": 0,
            "evacuated_population": 0,
            "submerged_area": 0,
            "description": "不漫滩"
        }
    
    if q >= 22000:
        _, pop, evac, area = SEGMENTS[-1]
        return {
            "garden_mouth_peak": q,
            "involved_population": pop,
            "evacuated_population": evac,
            "submerged_area": area,
            "description": "黄河滩区全部漫滩"
        }
    
    for i in range(len(SEGMENTS) - 1):
        q_low, pop_low, evac_low, area_low = SEGMENTS[i]
        q_high, pop_high, evac_high, area_high = SEGMENTS[i + 1]
        if q_low <= q <= q_high:
            ratio = (q - q_low) / (q_high - q_low) if q_high != q_low else 0
            pop = round(pop_low + ratio * (pop_high - pop_low), 2)
            evac = round(evac_low + ratio * (evac_high - evac_low), 2)
            area = round(area_low + ratio * (area_high - area_low), 2)
            return {
                "garden_mouth_peak": q,
                "involved_population": pop,
                "evacuated_population": evac,
                "submerged_area": area,
                "description": f"花园口洪峰{q:.0f}m³/s，滩区漫滩"
            }
    
    return {"garden_mouth_peak": q, "involved_population": 0, "evacuated_population": 0, "submerged_area": 0, "description": "未知"}


def check_dongpinghu_diversion(conn) -> dict:
    """从 Dispatch_Par 表读取东平湖分洪状态（stcd=1）"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT Control_Par FROM Dispatch_Par WHERE stcd = 1")
        row = cursor.fetchone()
        if row and row.Control_Par == 1:
            return {"enabled": True, "max_flow": 3600, "volume": 9.79}
        return {"enabled": False}
    except Exception as e:
        logger.warning(f"读取东平湖分洪状态失败: {e}")
        return {"enabled": False}