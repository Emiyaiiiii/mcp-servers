import json
import requests
from mcp.server.fastmcp import FastMCP
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_QY_BC = [2725.71, 2564.77, 2403.81, 2242.85, 2403.81, 2564.77, 2725.71, 2304.76, 1883.81, 1462.86, 1537.15, 1611.43, 1685.72, 1599.05, 1512.38, 1425.71, 1586.67, 1747.62, 1908.57, 1846.67, 1784.76, 1722.86, 1691.9, 1660.96, 1629.99, 1617.62, 1605.24, 1592.86, 1524.77, 1456.67, 1388.57, 1407.15, 1425.71, 1444.28, 1710.48, 1976.66, 2242.85, 2317.13, 2391.43, 2465.71, 2799.99, 3134.28, 3468.57, 3450, 3431.43, 3412.85, 3666.67, 3920.48, 4174.29, 4360.01, 4452.85, 4322.85, 4657.13, 5084.28, 5278.89, 5687.78, 5924.44, 5982.22, 6184.44, 6439.99, 6328.57, 6328.57, 6217.15, 6180, 6551.43, 6588.57, 6662.85, 6718.57, 6737.14, 7164.28, 7220, 7182.87, 7331.42, 7368.58, 7591.43, 7665.71, 7777.14, 7814.28, 8241.43, 8260, 8520, 8649.99, 8705.72, 8854.29, 8705.72, 8891.43, 9114.29, 9114.29, 9634.28, 9337.13, 9522.87, 9690, 9652.86, 9690, 9912.86, 9690, 9690, 9912.86, 9857.15, 10005.71, 9801.43, 10024.29, 9931.43, 9671.42, 9652.86, 9615.71, 9597.15, 9522.87, 8965.71, 8594.28, 7740.01, 6941.43, 6477.14, 5660, 5214.29, 4712.86, 4322.85, 3895.71, 3152.85, 3152.85, 2688.58, 2577.15, 2540, 3152.85, 3152.85, 2688.58, 2577.15, 2540, 1722.86, 2521.43, 2372.86, 1629.99, 1574.28, 1704.29, 1685.72, 1685.72, 1370, 1444.28, 1388.57, 1685.72, 1481.42, 1184.29, 1370, 1407.15, 1370, 1221.43, 1240, 1295.71, 1370, 1147.13, 980, 311.42, 330, 274.28, 237.15, 239.33, 385.71, 200, 255.71, 218.57, 367.15, 218.57, 274.28, 255.71, 330, 255.71, 422.86, 274.28]
DEFAULT_SW_BC = [265] * 168
DEFAULT_CK_BC = [20000] * 168
DEFAULT_QUJIAN_BC = [286, 277.33, 268.67, 260, 268.67, 277.33, 286, 263.33, 240.67, 218, 222, 226, 230, 225.33, 220.67, 216, 224.67, 233.33, 242, 238.67, 235.33, 232, 230.33, 228.67, 227, 226.33, 225.67, 225, 221.33, 217.67, 214, 215, 216, 217, 231.33, 245.67, 260, 264, 268, 272, 290, 308, 326, 325, 324, 323, 336.67, 350.33, 364, 374, 379, 372, 390, 413, 475, 645, 660, 514, 498, 486, 480, 480, 474, 472, 492, 494, 498, 501, 502, 525, 528, 526, 534, 536, 548, 552, 558, 560, 583, 584, 598, 605, 608, 616, 608, 618, 630, 630, 658, 642, 652, 661, 659, 661, 673, 661, 661, 673, 670, 678, 667, 679, 674, 660, 659, 657, 656, 652, 622, 602, 556, 513, 488, 444, 420, 393, 372, 349, 309, 309, 284, 278, 276, 309, 309, 284, 278, 276, 232, 275, 267, 227, 224, 231, 230, 230, 213, 217, 214, 230, 219, 203, 213, 215, 213, 205, 206, 209, 213, 201, 192, 156, 157, 154, 152, 137, 160, 150, 153, 151, 159, 151, 154, 153, 157, 153, 162, 154]

DEFAULT_QY_SW = [2300,2300,2300,2215,2130,2150,2170,2155,2140,2220,2300,2245,2190,2110,2030,2080,2130,2140,2150,2180,2210,2100,1990,2060,2130,2170,2210,2230,2250,2260,2270,2510,2750,2755,2760,2640,2520,2620,2720,3045,3370,4570,5770,5715,5660,5310,4960,4700,4440,4375,4310,4285,4260,4450,4640,4685,4730,4945,5160,5180,5200,5365,5530,5615,5700,5810,5920,6040,6160,6260,6360,6440,6520,6570,6620,6720,6820,6895,6970,7080,7190,7250,7310,7305,7300,7505,7710,7765,7820,7880,7880,7920,7960,7975,7990,8095,8200,8150,8100,8135,8170,8180,8190,8175,8160,8115,8070,8080,8090,8145,8200,8125,8050,7955,7860,7855,7850,7880,7910,7865,7820,7740,7660,7690,7720,7755,7790,7770,7750,7630,7510,7555,7600,7590,7580,7595,7610,7600,4320,3950,4200,4240,4310,4240,4220,4220,4070,4130,4110,4080,4140,4190,4190,4080,4080,4080,4080,4160,4220,4080,4040,4130,4000,3990,4070,3950,3930,3950]
DEFAULT_SW_SW = [258] * 168
DEFAULT_QUJIAN_SW = [230,230,230,221.5,213,215,217,215.5,214,222,230,224.5,219,211,203,208,213,214,215,218,221,210,199,206,213,217,221,223,225,226,227,251,275,275.5,276,264,252,262,272,304.5,337,457,577,571.5,566,531,496,470,444,437.5,431,428.5,426,445,464,468.5,473,494.5,516,518,520,536.5,553,561.5,570,581,592,604,616,626,636,644,652,657,662,672,682,689.5,697,708,719,725,731,730.5,730,750.5,771,776.5,782,788,788,792,796,797.5,799,809.5,820,815,810,813.5,817,818,819,817.5,816,811.5,807,808,809,814.5,820,812.5,805,795.5,786,785.5,785,788,791,786.5,782,774,766,769,772,775.5,779,777,775,763,751,755.5,760,759,758,759.5,761,760,432,395,420,424,431,424,422,422,407,413,411,408,414,419,419,408,408,408,408,416,422,408,404,413,400,399,407,395,393,395]

DEFAULT_ZV = [
    [181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275],
    [0, 0, 0, 1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 8, 10, 11, 13, 14, 16, 19, 21, 24, 27, 32, 38, 46, 54, 63, 74, 85, 99, 113, 128, 145, 162, 183, 209, 239, 273, 315, 363, 415, 471, 532, 599, 674, 751, 833, 918, 1006, 1099, 1196, 1296, 1401, 1511, 1628, 1752, 1881, 2014, 2152, 2294, 2442, 2596, 2754, 2916, 3082, 3252, 3425, 3603, 3784, 3968, 4155, 4346, 4541, 4738, 4938, 5142, 5350, 5561, 5775, 5992, 6213, 6438, 6666, 6898, 7134, 7373, 7615, 7861, 8110, 8364, 8620, 8880, 9144, 9411]
]

DEFAULT_ZQXL = [
    [230, 235, 240, 245, 250, 255, 260, 265, 270, 275, 280],
    [8148, 8849, 9547, 10110, 10672, 11106.625, 11716.3, 12911.7, 14504, 16429.3, 16429.3]
]


def register_reservoir_dispatch(mcp: FastMCP):
    @mcp.tool()
    async def run_xiaolangdi_compensation_dispatch(
        qy: str = None,
        sw: str = None,
        ck: str = None,
        qujian: str = None,
        num1: int = 168,
        zmin: float = 230.0,
        dq: float = 1500.0,
        dtt: int = 1,
        ze: float = 264.0,
        q0: float = 2000.0,
        z0: float = 260.5,
        time: str = "2021-10-01 00:00:00",
        last_time: int = 1,
        reservoir_id: str = "40104690",
        zv: str = None,
        zqxl: str = None
    ) -> dict:
        """
        调用小浪底水库补偿调度模式接口。

        Args:
            qy: 入流流量数据 (JSON格式数组)，单位m³/s，包含168个时段的入流流量，不传则使用默认数据
            sw: 水位数据 (JSON格式数组)，单位m，默认全为265m
            ck: 出库流量数据 (JSON格式数组)，单位m³/s，默认全为20000m³/s
            qujian: 区间流量数据 (JSON格式数组)，单位m³/s，包含168个时段的区间流量，不传则使用默认数据
            num1: 计算时段数，默认168（小时）
            zmin: 最小水位，单位m，默认230m
            dq: 泄流量，单位m³/s，默认1500m³/s
            dtt: 时间步长，单位小时，默认1小时
            ze: 控制水位，单位m，默认264m
            q0: 初始出库流量，单位m³/s，默认2000m³/s
            z0: 初始水位，单位m，默认260.5m
            time: 开始时间，格式"YYYY-MM-DD HH:MM:SS"，默认"2021-10-01 00:00:00"
            last_time: 末段时间标识，默认1
            reservoir_id: 水库ID，默认"40104690"（小浪底水库）
            zv: 水位库容曲线 (JSON格式二维数组)，[[水位值...], [库容值...]]，不传则使用默认曲线
            zqxl: 水位泄流曲线 (JSON格式二维数组)，[[水位值...], [泄流量值...]]，不传则使用默认曲线

        Returns:
            dict: 调度计算结果，包含以下字段：
                - success: bool类型，接口调用是否成功，True表示成功，False表示失败
                - command: str类型，命令标识，固定为"FUNC_RUN_COMPENSATION_DISPATCH"
                - reservoir: str类型，水库名称，固定为"小浪底水库"
                - dispatch_mode: str类型，调度模式，固定为"补偿调度模式"
                - result: dict类型，模型计算返回的原始结果数据（具体结构由下游模型决定）
                - message: str类型，执行结果描述信息
                - error: str类型（仅失败时存在），失败原因描述
        """
        logger.info(f"调用 run_xiaolangdi_compensation_dispatch，收到参数")

        try:
            qy_data = json.loads(qy) if isinstance(qy, str) and qy else DEFAULT_QY_BC
            sw_data = json.loads(sw) if isinstance(sw, str) and sw else DEFAULT_SW_BC
            ck_data = json.loads(ck) if isinstance(ck, str) and ck else DEFAULT_CK_BC
            qujian_data = json.loads(qujian) if isinstance(qujian, str) and qujian else DEFAULT_QUJIAN_BC
            zv_data = json.loads(zv) if isinstance(zv, str) and zv else DEFAULT_ZV
            zqxl_data = json.loads(zqxl) if isinstance(zqxl, str) and zqxl else DEFAULT_ZQXL
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "输入数据格式错误，请提供有效的JSON格式"}
            logger.info(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        try:
            url = "http://192.168.153.130:22811/bc"
            payload = {
                "qy": qy_data,
                "sw": sw_data,
                "ck": ck_data,
                "qujian": qujian_data,
                "num1": num1,
                "zmin": zmin,
                "dq": dq,
                "dtt": dtt,
                "ze": ze,
                "q0": q0,
                "z0": z0,
                "time": time,
                "lastTime": last_time,
                "id": reservoir_id,
                "zv": zv_data,
                "zqxl": zqxl_data
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()

            return_value = {
                "success": True,
                "command": "FUNC_RUN_COMPENSATION_DISPATCH",
                "reservoir": "小浪底水库",
                "dispatch_mode": "补偿调度模式",
                "result": result,
                "message": "小浪底水库补偿调度模式执行成功"
            }
            logger.info(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        except requests.exceptions.RequestException as e:
            logger.error(f"调用补偿调度接口失败: {str(e)}")
            return_value = {
                "success": False,
                "error": f"调用补偿调度接口失败: {str(e)}",
                "command": "FUNC_RUN_COMPENSATION_DISPATCH",
                "reservoir": "小浪底水库",
                "dispatch_mode": "补偿调度模式"
            }
            logger.info(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

    @mcp.tool()
    async def run_xiaolangdi_water_level_control(
        qy: str = None,
        sw: str = None,
        qujian: str = None,
        zmin: float = 230.0,
        num1: int = 168,
        dq: float = 1000.0,
        dtt: int = 1,
        ze: float = 257.0,
        q0: float = 1000.0,
        z0: float = 254.0,
        time: str = "2021-10-01 00:00:00",
        reservoir_id: str = "40104690",
        zv: str = None,
        zqxl: str = None
    ) -> dict:
        """
        调用小浪底水库水位控制模式接口。

        Args:
            qy: 入流流量数据 (JSON格式数组)，单位m³/s，包含168个时段的入流流量，不传则使用默认数据
            sw: 水位数据 (JSON格式数组)，单位m，默认全为258m
            qujian: 区间流量数据 (JSON格式数组)，单位m³/s，包含168个时段的区间流量，不传则使用默认数据
            zmin: 最小水位，单位m，默认230m
            num1: 计算时段数，默认168（小时）
            dq: 泄流量，单位m³/s，默认1000m³/s
            dtt: 时间步长，单位小时，默认1小时
            ze: 控制水位，单位m，默认257m
            q0: 初始出库流量，单位m³/s，默认1000m³/s
            z0: 初始水位，单位m，默认254m
            time: 开始时间，格式"YYYY-MM-DD HH:MM:SS"，默认"2021-10-01 00:00:00"
            reservoir_id: 水库ID，默认"40104690"（小浪底水库）
            zv: 水位库容曲线 (JSON格式二维数组)，[[水位值...], [库容值...]]，不传则使用默认曲线
            zqxl: 水位泄流曲线 (JSON格式二维数组)，[[水位值...], [泄流量值...]]，不传则使用默认曲线

        Returns:
            dict: 调度计算结果，包含以下字段：
                - success: bool类型，接口调用是否成功，True表示成功，False表示失败
                - command: str类型，命令标识，固定为"FUNC_RUN_WATER_LEVEL_CONTROL"
                - reservoir: str类型，水库名称，固定为"小浪底水库"
                - dispatch_mode: str类型，调度模式，固定为"水位控制模式"
                - result: dict类型，模型计算返回的原始结果数据（具体结构由下游模型决定）
                - message: str类型，执行结果描述信息
                - error: str类型（仅失败时存在），失败原因描述
        """
        logger.info(f"调用 run_xiaolangdi_water_level_control，收到参数")

        try:
            qy_data = json.loads(qy) if isinstance(qy, str) and qy else DEFAULT_QY_SW
            sw_data = json.loads(sw) if isinstance(sw, str) and sw else DEFAULT_SW_SW
            qujian_data = json.loads(qujian) if isinstance(qujian, str) and qujian else DEFAULT_QUJIAN_SW
            zv_data = json.loads(zv) if isinstance(zv, str) and zv else DEFAULT_ZV
            zqxl_data = json.loads(zqxl) if isinstance(zqxl, str) and zqxl else DEFAULT_ZQXL
        except json.JSONDecodeError:
            return_value = {"success": False, "error": "输入数据格式错误，请提供有效的JSON格式"}
            logger.info(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        try:
            url = "http://192.168.153.130:22811/sw"
            payload = {
                "qy": qy_data,
                "sw": sw_data,
                "qujian": qujian_data,
                "zmin": zmin,
                "num1": num1,
                "dq": dq,
                "dtt": dtt,
                "ze": ze,
                "q0": q0,
                "z0": z0,
                "time": time,
                "id": reservoir_id,
                "zv": zv_data,
                "zqxl": zqxl_data
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()

            return_value = {
                "success": True,
                "command": "FUNC_RUN_WATER_LEVEL_CONTROL",
                "reservoir": "小浪底水库",
                "dispatch_mode": "水位控制模式",
                "result": result,
                "message": "小浪底水库水位控制模式执行成功"
            }
            logger.info(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        except requests.exceptions.RequestException as e:
            logger.error(f"调用水位控制接口失败: {str(e)}")
            return_value = {
                "success": False,
                "error": f"调用水位控制接口失败: {str(e)}",
                "command": "FUNC_RUN_WATER_LEVEL_CONTROL",
                "reservoir": "小浪底水库",
                "dispatch_mode": "水位控制模式"
            }
            logger.info(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value