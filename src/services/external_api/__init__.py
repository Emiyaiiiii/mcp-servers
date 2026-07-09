"""外部 API 服务模块

提供与外部系统交互的认证和服务：
- 数据 API (auth_service)
- 来水预报 API (water_forecast_service)
- 增强搜索 API (enhanced_search_service)
- 新安江模型 API (xinanjiang_service)
- 水文局预报 API (hydrology_forecast_service)
"""

from src.services.external_api.auth_service import auth_service, AuthService
from src.services.external_api.water_forecast_service import (
    water_forecast_auth_service,
    WaterForecastAuthService,
    water_forecast_service,
    WaterForecastService
)
from src.services.external_api.enhanced_search_service import (
    enhanced_search_auth_service,
    EnhancedSearchAuthService,
    enhanced_search_service,
    EnhancedSearchService
)
from src.services.external_api.xinanjiang_service import (
    xinanjiang_auth_service,
    XinanjiangAuthService,
    xinanjiang_model_service,
    XinanjiangModelService
)
from src.services.external_api.hydrology_forecast_service import (
    hydrology_forecast_service,
    HydrologyForecastService
)

__all__ = [
    # 数据 API
    'auth_service',
    'AuthService',
    # 来水预报 API
    'water_forecast_auth_service',
    'WaterForecastAuthService',
    'water_forecast_service',
    'WaterForecastService',
    # 增强搜索 API
    'enhanced_search_auth_service',
    'EnhancedSearchAuthService',
    'enhanced_search_service',
    'EnhancedSearchService',
    # 新安江模型 API
    'xinanjiang_auth_service',
    'XinanjiangAuthService',
    'xinanjiang_model_service',
    'XinanjiangModelService',
    # 水文局预报 API
    'hydrology_forecast_service',
    'HydrologyForecastService',
]
