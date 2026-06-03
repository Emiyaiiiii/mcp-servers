"""统一的返回格式工具

提供统一的返回格式构建函数，确保所有工具返回的数据格式一致。

成功返回格式：
{
    "success": True,
    "command": "FUNC_XXX",
    "message": "操作描述（可选）",
    "response": {...},  # 原始响应
    # ... 其他业务字段
}

错误返回格式：
{
    "success": False,
    "error": "错误描述"
}
"""

from typing import Dict, Any, Optional


def success_response(
    command: str,
    response: Any,
    message: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """构建成功响应

    Args:
        command: 指令名称
        response: 原始响应
        message: 操作描述（可选）
        **kwargs: 其他业务字段

    Returns:
        统一格式的成功响应
    """
    result = {
        "success": True,
        "command": command,
        "response": response
    }
    if message:
        result["message"] = message
    result.update(kwargs)
    return result


def error_response(
    error: str,
    **kwargs
) -> Dict[str, Any]:
    """构建错误响应

    Args:
        error: 错误描述
        **kwargs: 其他业务字段

    Returns:
        统一格式的错误响应
    """
    result = {
        "success": False,
        "error": error
    }
    result.update(kwargs)
    return result
