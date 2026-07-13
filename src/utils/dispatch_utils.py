from typing import Dict, Any, List
from src.utils.logger import get_logger
from src.services.storage.database.data_access import (
    WaterLevelAccess, CoefficientAccess, HolePriorityAccess
)

logger = get_logger(__name__)


def get_water_level_config(reservoir_code: str, level: float) -> dict:
    """从数据库获取水位-流量配置"""
    config = WaterLevelAccess.get_by_level(reservoir_code, level)
    if not config:
        logger.warning(f"未找到水位配置: {reservoir_code}, {level}")
    return config or {}


def get_coefficient_table(reservoir_code: str, level_range: str) -> list:
    """从数据库获取调度系数表"""
    return CoefficientAccess.get_by_level_range(reservoir_code, level_range)


def get_dikong_order(reservoir_code: str) -> list:
    """从数据库获取底孔优先级顺序"""
    return HolePriorityAccess.get_priority_order(reservoir_code)


def generate_xiaolangdi_scheme_core(
    date: str,
    liu_liang: float,
    shui_wei: float,
    han_sha_liang: float
) -> dict:
    """
    生成小浪底水库机组孔洞调度方案。

    Args:
        date: 日期时间，格式: yyyy-MM-dd HH:mm:ss
        liu_liang: 出库流量（m³/s）
        shui_wei: 当前水位（m）
        han_sha_liang: 含沙量（kg/m³）

    Returns:
        调度方案建议，包含推荐方案描述
    """
    try:
        q = int(round(liu_liang))
        wl = shui_wei
        sand = han_sha_liang

        cfg = get_water_level_config("XLD", wl)

        if not cfg or not cfg.get("hole_details"):
            return {"date": date, "tuijianfangan": "水位不匹配，无法生成调度方案"}

        stop_turb = wl < 215 or sand > 20

        if stop_turb:
            turb_txt = "根据当前机组状态推荐全停，结合实际调整机组。"
            hole_target = q
        else:
            turb_txt = "根据当前机组状态推荐全开6台机组，每台300m³/s，合计1800m³/s，结合实际调整。"
            hole_target = max(q - 1800, 0)

        holes = cfg.get("hole_details", [])

        total = 0
        used = []
        hole_list = []
        for hole in holes:
            if total >= hole_target:
                break
            max_flow = hole.get("流量", 0)
            take = min(max_flow, hole_target - total)
            hole_number = hole.get("编号", "")
            hole_index = int(hole_number.replace("号", "").replace("洞", "")) if hole_number else 0
            used.append((hole.get("type", "未知"), hole_number, take))
            hole_list.append({
                "type": hole.get("type"),
                "number": hole_number,
                "index": hole_index,
                "flow": take,
                "max_flow": max_flow
            })
            total += take

        if not used:
            hole_txt = "无需开启孔洞"
        else:
            group = {}
            for hole_type, number, value in used:
                group.setdefault(hole_type, []).append(f"{number}：{value}m³/s")

            parts = []
            for hole_type in ["排沙洞", "孔板洞", "明流洞"]:
                if hole_type in group:
                    parts.append(f"{len(group[hole_type])}条{hole_type}（{', '.join(group[hole_type])}）")

            last_type, last_number, last_value = used[-1]
            for hole in holes:
                if hole.get("编号") == last_number:
                    max_flow = hole.get("流量", 0)
                    if last_value < max_flow:
                        parts.append(f"{last_number}{last_type}剩余流量补足：{last_value}m³/s")
                    break

            hole_txt = "，".join(parts)

        reason = f"因为当前泥沙含量为{sand}kg/m³，水位是{wl}m，出库流量为{q}m³/s，{turb_txt}根据孔洞检修情况推荐：{hole_txt}，结合实际调整。"
        return {
            "date": date,
            "tuijianfangan": reason,
            "holes": hole_list,
            "total_flow": total,
            "unit_status": "全停" if stop_turb else "全开6台机组"
        }

    except Exception as e:
        error_msg = f"生成调度方案时出错: {str(e)}"
        logger.error(error_msg)
        return {"date": date, "tuijianfangan": f"生成调度方案失败: {error_msg}"}


def generate_sanmenxia_scheme_core(
    date: str,
    liu_liang: float,
    shui_wei: float,
    han_sha_liang: float
) -> dict:
    """
    生成三门峡水库机组孔洞调度方案。

    Args:
        date: 日期时间，格式: yyyy-MM-dd HH:mm:ss
        liu_liang: 出库流量（m³/s）
        shui_wei: 当前水位（m）
        han_sha_liang: 含沙量（kg/m³）

    Returns:
        调度方案建议，包含推荐方案描述及各部件状态
    """
    try:
        q_total = round(liu_liang)
        wl = shui_wei
        sand = han_sha_liang

        cfg = get_water_level_config("SMX", wl)

        if not cfg:
            return {"date": date, "tuijianfangan": "水位不匹配，无法生成调度方案"}

        q_dk = round(cfg.get("bottom_hole_flow", 0))
        q_sk = round(cfg.get("deep_hole_flow", 0))
        q_sd_full = cfg.get("tunnel_flow", 0)

        scene1 = wl < 302 or sand > 60
        jizu_text = ""
        q_jz = 0
        req = q_total

        if scene1:
            jizu_text = "根据当前泥沙含量和水位条件推荐机组全停"
            q_jz = 0
            req = q_total
        else:
            if wl > 322:
                jizu_text = "水位>322m，机组全部关停，仅使用底孔、隧洞、深孔、钢管泄流"
                scene1 = True
                q_jz = 0
                req = q_total
            elif 302 <= wl < 312:
                if q_total < 1200:
                    q_jz = q_total
                    jizu_text = f"推荐5台机组运行，合计{q_jz}m³/s，无需开启孔洞"
                else:
                    q_jz = 1200
                    jizu_text = f"推荐5台机组满负荷运行，合计{q_jz}m³/s"
            elif 312 <= wl < 314:
                if q_total < 1500:
                    q_jz = q_total
                    jizu_text = f"推荐7台机组运行，合计{q_jz}m³/s，无需开启孔洞"
                else:
                    q_jz = 1500
                    jizu_text = f"推荐7台机组满负荷运行，合计{q_jz}m³/s"
            else:
                if q_total < 1300:
                    q_jz = q_total
                    jizu_text = f"推荐7台机组运行，合计{q_jz}m³/s，无需开启孔洞"
                else:
                    q_jz = 1300
                    jizu_text = f"推荐7台机组满负荷运行，合计{q_jz}m³/s"
            if not scene1:
                req = max(q_total - q_jz, 0)

        dk_list = []
        sk_list = []
        sd_q = 0
        sd_open = 0.0
        sk_text = "无需开启深孔"

        dikong_order = get_dikong_order("SMX")
        if not dikong_order:
            dikong_order = list(range(1, 13))

        if req > 0:
            for no in dikong_order:
                if req >= q_dk:
                    dk_list.append((no, q_dk))
                    req -= q_dk
                else:
                    break

            if req > 0 and q_sk > 0:
                for no in range(1, 13):
                    if req >= q_sk:
                        sk_list.append((no, q_sk))
                        req -= q_sk
                    else:
                        break
                if sk_list:
                    sk_text = f"开启{len(sk_list)}条深孔（{', '.join([f'{n}号深孔：{q}m³/s' for n, q in sk_list])}），合计{sum(q for _, q in sk_list)}m³/s"

            if req > 0 and q_sd_full > 0:
                sd_q = req
                if 300 <= wl <= 310:
                    coeff_key = "300-310"
                elif 311 <= wl <= 315:
                    coeff_key = "311-315"
                else:
                    coeff_key = "315以上"

                coeff_rules = get_coefficient_table("SMX", coeff_key)
                if coeff_rules:
                    n_est = (sd_q * 8) / (q_sd_full * 0.9)
                    for rule in coeff_rules:
                        low, high = rule["range_min"], rule["range_max"]
                        k = rule["coeff_value"]
                        n = (sd_q * 8) / (q_sd_full * k)
                        if low <= round(n, 2) <= high:
                            sd_open = round(n, 1)
                            break
                    else:
                        sd_open = round((sd_q * 8) / q_sd_full, 1)
                else:
                    sd_open = round((sd_q * 8) / q_sd_full, 1)

        dk_items = [f"{n}号底孔：{q}m³/s" for n, q in dk_list]
        dk_count = len(dk_list)
        dk_sum = sum(q for _, q in dk_list)
        dikong_text = f"开启{dk_count}条底孔（{', '.join(dk_items)}），合计{dk_sum}m³/s" if dk_count else "无需开启底孔"

        sk_sum = sum(q for _, q in sk_list)

        if sd_q > 0:
            single_tunnel_flow = q_sd_full
            if sd_q <= single_tunnel_flow:
                suidong_text = f"开启1号隧洞，开度{sd_open}m，流量{sd_q}m³/s"
            else:
                first_flow = min(sd_q, single_tunnel_flow)
                second_flow = sd_q - first_flow
                first_open = sd_open
                second_open = round((second_flow * 8) / single_tunnel_flow, 1)
                suidong_text = f"开启1号隧洞（开度{first_open}m，流量{first_flow}m³/s）、2号隧洞（开度{second_open}m，流量{second_flow}m³/s），合计{sd_q}m³/s"
        else:
            suidong_text = "无需开启隧洞"

        tuan = []
        if dk_list:
            tuan.append(dikong_text.split("，")[0])
        if sk_list:
            tuan.append(sk_text.split("，")[0])
        if sd_q:
            tuan.append(suidong_text)
        hole_str = "，".join(tuan) if tuan else "无需开启泄流孔洞"

        tui = f"因为当前泥沙含量为{sand}kg/m³，水位是{wl}m，出库流量为{q_total}m³/s，{jizu_text}，结合实际调整机组。根据孔洞检修情况推荐：{hole_str}，结合实际调整。"

        hole_list = []
        for no, q in dk_list:
            hole_list.append({
                "type": "底孔",
                "number": f"{no}号",
                "index": no,
                "flow": q,
                "max_flow": q_dk
            })
        for no, q in sk_list:
            hole_list.append({
                "type": "深孔",
                "number": f"{no}号",
                "index": no,
                "flow": q,
                "max_flow": q_sk
            })
        if sd_q > 0:
            single_tunnel_flow = q_sd_full

            if sd_q <= single_tunnel_flow:
                hole_list.append({
                    "type": "隧洞",
                    "number": "1号",
                    "index": 1,
                    "flow": sd_q,
                    "opening": sd_open,
                    "max_flow": single_tunnel_flow
                })
            else:
                remaining_flow = sd_q
                tunnel_count = 1

                while remaining_flow > 0 and tunnel_count <= 2:
                    tunnel_flow = min(remaining_flow, single_tunnel_flow)
                    hole_list.append({
                        "type": "隧洞",
                        "number": f"{tunnel_count}号",
                        "index": tunnel_count,
                        "flow": tunnel_flow,
                        "opening": sd_open if tunnel_count == 1 else round((tunnel_flow * 8) / single_tunnel_flow, 1),
                        "max_flow": single_tunnel_flow
                    })
                    remaining_flow -= tunnel_flow
                    tunnel_count += 1

        return {
            "date": date,
            "tuijianfangan": tui,
            "jizu": jizu_text + "，结合实际调整",
            "dikong": dikong_text,
            "shenkong": sk_text,
            "suidong": suidong_text,
            "holes": hole_list,
            "total_flow": dk_sum + sk_sum + sd_q,
            "unit_status": "全停" if scene1 else "部分运行"
        }

    except Exception as e:
        error_msg = f"生成调度方案时出错: {str(e)}"
        logger.error(error_msg)
        return {"date": date, "tuijianfangan": f"生成调度方案失败: {error_msg}"}