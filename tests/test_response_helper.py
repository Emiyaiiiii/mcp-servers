"""
测试 response_helper.py 的统一响应格式
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from src.utils.response_helper import success_response, error_response


class TestSuccessResponse:
    def test_basic(self):
        result = success_response("FUNC_TEST", {"data": "test"})
        assert result["success"] is True
        assert result["command"] == "FUNC_TEST"
        assert result["response"] == {"data": "test"}

    def test_with_message(self):
        result = success_response("FUNC_TEST", "ok", message="操作成功")
        assert result["success"] is True
        assert result["message"] == "操作成功"

    def test_with_extra_kwargs(self):
        result = success_response("FUNC_TEST", "ok", extra_field="value")
        assert result["extra_field"] == "value"


class TestErrorResponse:
    def test_basic(self):
        result = error_response("出错了")
        assert result["success"] is False
        assert result["error"] == "出错了"

    def test_with_extra(self):
        result = error_response("出错了", code=500)
        assert result["code"] == 500