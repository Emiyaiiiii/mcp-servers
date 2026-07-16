"""
测试 mdb_utils.py 中的工具函数
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from src.utils.dispatch.mdb_utils import get_dispatch_mdb_path, get_mdb_driver_name, mdb_execute


class TestMdbUtils:
    def test_get_dispatch_mdb_path(self):
        """测试 MDB 路径生成"""
        path = get_dispatch_mdb_path()
        assert path.endswith('data.mdb')
        assert 'RegualDispacth' in path

    def test_get_mdb_driver_name(self):
        """测试驱动名获取（Windows下返回 Access 驱动）"""
        driver = get_mdb_driver_name()
        assert driver is not None
        assert len(driver) > 0