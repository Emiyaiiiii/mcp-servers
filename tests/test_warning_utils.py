"""
测试 warning_utils.py 中的预警等级判定逻辑
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from src.utils.analysis.warning_utils import (
    get_xiaolangdi_warning_core,
    get_sanmenxia_warning_core,
    get_yellow_river_emergency_response_core
)


class TestXiaolangdiWarning:
    """测试小浪底预警等级判定"""

    def test_no_warning(self):
        """低水位低流量：无预警"""
        result = get_xiaolangdi_warning_core(tongguan_flow=1000, reservoir_level=230, outflow_flow=1000)
        assert result["warning_level"] in ["无预警", "I级响应", "II级响应", "III级响应", "IV级响应"]

    def test_high_level_warning(self):
        """高水位高流量：高等级预警"""
        result = get_xiaolangdi_warning_core(tongguan_flow=8000, reservoir_level=270, outflow_flow=5000)
        assert result["warning_level"] in ["I级响应", "II级响应", "III级响应", "IV级响应"]


class TestSanmenxiaWarning:
    """测试三门峡预警等级判定"""

    def test_no_warning(self):
        """低流量：无预警"""
        result = get_sanmenxia_warning_core(longmen_flow=1000, tongguan_flow=800, huaxian_flow=500)
        assert result["warning_level"] in ["无预警", "I级响应", "II级响应", "III级响应", "IV级响应"]

    def test_high_flow(self):
        """高流量：有预警"""
        result = get_sanmenxia_warning_core(longmen_flow=12000, tongguan_flow=8000, huaxian_flow=5000)
        assert result["warning_level"] in ["I级响应", "II级响应", "III级响应", "IV级响应"]


class TestYellowRiverEmergencyResponse:
    """测试黄河应急响应等级判定"""

    def test_all_low(self):
        """所有参数较低：无响应"""
        result = get_yellow_river_emergency_response_core(
            xld_level=240, smx_level=310, hxk_level=250,
            hx_level=240, ht_level=240, lk_level=240,
            tongguan=1000, huayuankou=1500, huaxian=500,
            longmen=800, sanmenxia=1000, xiaolangdi=500,
            wuzhi=800, qinhe=300, zhuangtou=200,
            daima=600, dongkoutou=200
        )
        assert result["warning_level"] in ["无预警", "I级响应", "II级响应", "III级响应", "IV级响应"]