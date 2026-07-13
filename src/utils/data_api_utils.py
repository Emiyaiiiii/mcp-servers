import requests
from typing import Dict, Any, Optional
from src.config.settings import settings
from src.utils.station_codes import get_reservoir_code, get_station_code
from src.services.external_api.data_api_auth_service import data_api_auth_service
from src.utils.date_utils import format_date_fields
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = settings.DATA_API_BASE_URL
TIMEOUT = 30

_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def resolve_reservoir(name_or_code: str) -> str | None:
    if not name_or_code:
        return None
    code = get_reservoir_code(name_or_code)
    if code:
        return code
    return name_or_code if name_or_code else None


def resolve_station(name_or_code: str) -> str | None:
    if not name_or_code:
        return None
    code = get_station_code(name_or_code)
    if code:
        return code
    return name_or_code if name_or_code else None


def resolve_reservoir_for_api(name_or_code: str) -> str | None:
    if not name_or_code:
        return None
    station_code = get_reservoir_code(name_or_code)
    if not station_code:
        return name_or_code
    return station_code


def api_get(url: str, params: Dict[str, Any] | None = None, retry_with_auth: bool = True) -> Dict[str, Any]:
    try:
        session = _get_session()
        headers = data_api_auth_service.get_auth_headers()
        
        auth_val = headers.get("Authorization", "")
        logger.info(f"api_get 请求 [url={url}, has_auth={bool(auth_val)}, auth_prefix={auth_val[:20] if auth_val else 'N/A'}]")

        response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)

        logger.info(f"api_get 响应 [status={response.status_code}, body_prefix={response.text[:200]}]")

        if response.status_code == 401 and retry_with_auth:
            logger.warning("Token过期或无效，正在重新登录...")
            data_api_auth_service.clear_token()
            headers = data_api_auth_service.get_auth_headers()
            if headers:
                logger.info("api_get 使用新token重试请求")
                response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
                logger.info(f"api_get 重试响应 [status={response.status_code}, body_prefix={response.text[:200]}]")

        response.raise_for_status()
        result = response.json()

        if result.get("code") == 401 and retry_with_auth:
            logger.warning("API返回认证错误，正在重新登录...")
            data_api_auth_service.clear_token()
            headers = data_api_auth_service.get_auth_headers()
            if headers:
                logger.info("api_get 使用新token重试请求(业务层)")
                response = session.get(url, params=params, headers=headers, timeout=TIMEOUT)
                response.raise_for_status()
                result = response.json()
                logger.info(f"api_get 业务重试响应 [body_prefix={response.text[:200]}]")

        return format_date_fields(result)

    except requests.exceptions.RequestException as e:
        logger.error(f"请求异常: {e}")
        return {"code": 500, "data": None, "msg": str(e)}
