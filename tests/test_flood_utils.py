"""
测试 flood_utils.py 中的淹没分析逻辑
重点关注修复后的分界点 Bug
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# 测试前需要 mock 掉 logger 和外部依赖
from unittest.mock import patch, MagicMock
from src.utils.analysis.flood_utils import get_flood_submerge_core, get_risk_by_huayuankou_flow_core


class TestGetFloodSubmerge:
    """测试 get_flood_submerge_core 的分界点逻辑"""

    def test_below_6000(self):
        """q < 6000：无淹没"""
        result = get_flood_submerge_core(5000)
        assert result["level"] == "<6000 m³/s"

    def test_6000_boundary(self):
        """q = 6000：开始漫滩"""
        result = get_flood_submerge_core(6000)
        assert result["level"] == "6000 m³/s"

    def test_6000_to_8000(self):
        """q = 7000：6000 级别"""
        result = get_flood_submerge_core(7000)
        assert result["level"] == "6000 m³/s"

    def test_8000_boundary_lower(self):
        """q = 8000：8000 级别（修复后的关键分界点）"""
        result = get_flood_submerge_core(8000)
        assert result["level"] == "8000 m³/s"

    def test_8000_to_10000(self):
        """q = 9000：8000 级别"""
        result = get_flood_submerge_core(9000)
        assert result["level"] == "8000 m³/s"

    def test_10000_boundary(self):
        """q = 10000：10000 级别"""
        result = get_flood_submerge_core(10000)
        assert result["level"] == "10000 m³/s"

    def test_12370_boundary(self):
        """q = 12370：12370 级别"""
        result = get_flood_submerge_core(12370)
        assert result["level"] == "12370 m³/s"

    def test_15700_boundary_lower(self):
        """q = 15700：15700~22000 级别"""
        result = get_flood_submerge_core(15700)
        assert result["level"] == "15700~22000 m³/s（大洪水）"

    def test_22000_boundary(self):
        """q = 22000：≥22000 级别"""
        result = get_flood_submerge_core(22000)
        assert result["level"] == "≥22000 m³/s"

    def test_very_high(self):
        """q = 30000：≥22000 级别"""
        result = get_flood_submerge_core(30000)
        assert result["level"] == "≥22000 m³/s"


class TestGetRiskByHuayuankouFlow:
    """测试 get_risk_by_huayuankou_flow_core 的边界条件"""

    def test_below_4000(self):
        """q = 3000：小于4000，无出险"""
        result = get_risk_by_huayuankou_flow_core(3000)
        assert result["level"] == "小于4000"
        assert result["risk"] is False

    def test_4000_to_6000(self):
        """q = 5000：4000~6000"""
        result = get_risk_by_huayuankou_flow_core(5000)
        assert result["level"] == "4000~6000"

    def test_6000_to_8000(self):
        """q = 7000：6000~8000"""
        result = get_risk_by_huayuankou_flow_core(7000)
        assert result["level"] == "6000~8000"

    def test_8000_to_10000(self):
        """q = 9000：8000~10000"""
        result = get_risk_by_huayuankou_flow_core(9000)
        assert result["level"] == "8000~10000"

    def test_10000_to_15000(self):
        """q = 12000：10000~15000"""
        result = get_risk_by_huayuankou_flow_core(12000)
        assert result["level"] == "10000~15000"

    def test_15000_to_22000(self):
        """q = 18000：15000~22000"""
        result = get_risk_by_huayuankou_flow_core(18000)
        assert result["level"] == "15000~22000"

    def test_above_22000(self):
        """q = 25000：大于22000"""
        result = get_risk_by_huayuankou_flow_core(25000)
        assert result["level"] == "大于22000"