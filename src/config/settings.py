import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    MCP_SERVER_NAME = os.getenv('MCP_SERVER_NAME', 'FloodControlMCP')

    SCENE_WS_BASE_URL = os.getenv('SCENE_WS_BASE_URL', 'ws://localhost:8889')
    SCENE_WS_TIMEOUT = int(os.getenv('SCENE_WS_TIMEOUT', '30'))
    SCENE_IDLE_TIMEOUT = int(os.getenv('SCENE_IDLE_TIMEOUT', '60'))

    DATA_API_BASE_URL = os.getenv('DATA_API_BASE_URL', 'http://wt.hxyai.cn/fx')
    DATA_API_ACCESS_KEY = os.getenv('DATA_API_ACCESS_KEY', 'yhllm')
    DATA_API_SECRETKEY = os.getenv('DATA_API_SECRETKEY', '5f75d154f9cc50ad0ad8790d0a7f5301')
    DATA_API_MOCK_ENABLED = os.getenv('DATA_API_MOCK_ENABLED', 'true').lower() == 'true'

    KNOWLEDGE_BASE_API_URL = os.getenv('KNOWLEDGE_BASE_API_URL', 'http://10.4.158.35:9621/query/data')

    DISPATCH_API_BC_URL = os.getenv('DISPATCH_API_BC_URL', 'http://localhost:22811/bc')
    DISPATCH_API_SW_URL = os.getenv('DISPATCH_API_SW_URL', 'http://localhost:22811/sw')

    ENHANCED_SEARCH_API_BASE_URL = os.getenv('ENHANCED_SEARCH_API_BASE_URL', 'https://10.4.158.43:18888')
    ENHANCED_SEARCH_API_USERNAME = os.getenv('ENHANCED_SEARCH_API_USERNAME', '4055036')
    ENHANCED_SEARCH_API_PASSWORD = os.getenv('ENHANCED_SEARCH_API_PASSWORD', '20221qaz@WSX')

    HYDROLOGY_API_BASE_URL = os.getenv('HYDROLOGY_API_BASE_URL', 'http://10.4.158.35:8091')
    HYDROLOGY_API_USERNAME = os.getenv('HYDROLOGY_API_USERNAME', 'yh')
    HYDROLOGY_API_PASSWORD = os.getenv('HYDROLOGY_API_PASSWORD', 'Ylhfxsy@2026!@#')
    HYDROLOGY_API_CLIENT_ID = os.getenv('HYDROLOGY_API_CLIENT_ID', 'e5cd7e4891bf95d1d19206ce24a7b32e')

    WATER_FORECAST_API_BASE_URL = os.getenv('WATER_FORECAST_API_BASE_URL', 'http://10.4.158.37:11111')
    WATER_FORECAST_API_USERNAME = os.getenv('WATER_FORECAST_API_USERNAME', 'yh')
    WATER_FORECAST_API_PASSWORD = os.getenv('WATER_FORECAST_API_PASSWORD', 'Yrec!@#2025')
    WATER_FORECAST_API_CLIENT_ID = os.getenv('WATER_FORECAST_API_CLIENT_ID', 'e5cd7e4891bf95d1d19206ce24a7b32e')

    XINANJIANG_API_BASE_URL = os.getenv('XINANJIANG_API_BASE_URL', 'http://gateway.yrihr.com')
    XINANJIANG_APP_KEY = os.getenv('XINANJIANG_APP_KEY', 'mcp-app-nwryet8fz86wv7qnfdym')
    XINANJIANG_APP_SECRET = os.getenv('XINANJIANG_APP_SECRET', '7p899yn2gxf9dx9t430uqy1xwtkgo9p06o1h7quh7nm36wg8lj')

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    MCP_AUTH_ENABLED = os.getenv('MCP_AUTH_ENABLED', 'false').lower() == 'true'
    MCP_AUTH_MODE = os.getenv('MCP_AUTH_MODE', 'api_key')
    MCP_AUTH_API_KEY = os.getenv('MCP_AUTH_API_KEY', '')

    # JWT Verification Configuration
    MCP_JWT_MODE = os.getenv('MCP_JWT_MODE', 'api_key')  # jwks, public_key, hmac, api_key
    MCP_JWKS_URI = os.getenv('MCP_JWKS_URI', '')
    MCP_JWT_ISSUER = os.getenv('MCP_JWT_ISSUER', '')
    MCP_JWT_AUDIENCE = os.getenv('MCP_JWT_AUDIENCE', '')
    MCP_JWT_ALGORITHM = os.getenv('MCP_JWT_ALGORITHM', 'RS256')
    MCP_JWT_PUBLIC_KEY = os.getenv('MCP_JWT_PUBLIC_KEY', '')
    MCP_JWT_SECRET = os.getenv('MCP_JWT_SECRET', '')

    MCP_SERVER_BASE_URL = os.getenv('MCP_SERVER_BASE_URL', 'http://localhost:8082')
    MCP_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv('MCP_ALLOWED_ORIGINS', '*').split(',') if origin.strip()]

    MCP_OAUTH_USERS = os.getenv('MCP_OAUTH_USERS', '')

    RAINFALL_SIMILARITY_API_URL = os.getenv('RAINFALL_SIMILARITY_API_URL', 'http://36.99.160.89:8066')
    RAINFALL_SIMILARITY_RASTER_URL = os.getenv('RAINFALL_SIMILARITY_RASTER_URL', 'http://36.99.160.89:10017')

    # SSL 验证配置
    SSL_CERT_PATH = os.getenv('SSL_CERT_PATH', '')
    SSL_VERIFY = os.getenv('SSL_VERIFY', 'false').lower() == 'true'

    # API 限流配置
    RATE_LIMIT_MAX_REQUESTS = int(os.getenv('RATE_LIMIT_MAX_REQUESTS', '60'))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '60'))

settings = Settings()
