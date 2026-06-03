import json
import requests
from mcp.server.fastmcp import FastMCP
from src.utils.logger import get_logger
from src.services.storage.database.data_access import SimulationParamsAccess, LevelCapacityCurveAccess, LevelFlowCurveAccess
from src.config.settings import settings

logger = get_logger(__name__)

DEFAULT_QY_BC = SimulationParamsAccess.get_param('XLD_QY_BC')
DEFAULT_SW_BC = SimulationParamsAccess.get_param('XLD_SW_BC')
DEFAULT_CK_BC = SimulationParamsAccess.get_param('XLD_CK_BC')
DEFAULT_QUJIAN_BC = SimulationParamsAccess.get_param('XLD_QUJIAN_BC')

DEFAULT_QY_SW = SimulationParamsAccess.get_param('XLD_QY_SW')
DEFAULT_SW_SW = SimulationParamsAccess.get_param('XLD_SW_SW')
DEFAULT_QUJIAN_SW = SimulationParamsAccess.get_param('XLD_QUJIAN_SW')

DEFAULT_ZV = SimulationParamsAccess.get_param('XLD_ZV')
DEFAULT_ZQXL = SimulationParamsAccess.get_param('XLD_ZQXL')


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
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        if qy_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QY_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if sw_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_SW_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if ck_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_CK_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if qujian_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QUJIAN_BC参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if zv_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZV参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value
        if zqxl_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZQXL参数，请先配置"}
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
            return return_value

        try:
            url = settings.DISPATCH_API_BC_URL
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
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
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
            logger.debug(f"run_xiaolangdi_compensation_dispatch 返回结果: {return_value}")
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
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        if qy_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QY_SW参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if sw_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_SW_SW参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if qujian_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_QUJIAN_SW参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if zv_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZV参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value
        if zqxl_data is None:
            return_value = {"success": False, "error": "数据库中未配置XLD_ZQXL参数，请先配置"}
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value

        try:
            url = settings.DISPATCH_API_SW_URL
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
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
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
            logger.debug(f"run_xiaolangdi_water_level_control 返回结果: {return_value}")
            return return_value