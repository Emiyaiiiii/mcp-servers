from fastmcp.server.auth import TokenVerifier, AccessToken
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ApiKeyVerifier(TokenVerifier):
    def __init__(self, base_url: str = None):
        super().__init__(base_url=base_url)
        self._valid_api_keys = self._load_valid_api_keys()

    def _load_valid_api_keys(self) -> set:
        api_keys = []
        if settings.MCP_AUTH_API_KEY:
            api_keys.append(settings.MCP_AUTH_API_KEY)
        return set(api_keys)

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            logger.warning("Empty token provided")
            return None

        if token in self._valid_api_keys:
            logger.info(f"Token verified successfully")
            return AccessToken(
                token=token,
                client_id="mcp_client",
                scopes=["mcp_access"],
                expires_at=None,
                claims={"role": "mcp_user"}
            )
        else:
            logger.warning(f"Invalid token provided")
            return None