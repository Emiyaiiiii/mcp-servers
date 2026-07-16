"""
测试 station_codes.py 中的站点编码匹配逻辑
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from src.utils.station_codes import get_reservoir_code, get_station_code


class TestStationCodes:
    def test_get_reservoir_code_xld(self):
        """小浪底编码解析"""
        code = get_reservoir_code("小浪底")
        assert code is not None

    def test_get_reservoir_code_smx(self):
        """三门峡编码解析"""
        code = get_reservoir_code("三门峡")
        assert code is not None

    def test_get_station_code_hyk(self):
        """花园口站编码解析"""
        code = get_station_code("花园口")
        assert code is not None

    def test_get_station_code_unknown(self):
        """未知站点"""
        code = get_station_code("不存在的站点")
        assert code is None