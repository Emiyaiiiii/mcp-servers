from fastmcp.server.auth import OAuthProvider, TokenVerifier, AccessToken
from mcp.shared.auth import OAuthClientInformationFull
from mcp.server.auth.handlers.authorize import AuthorizationParams
from mcp.server.auth.provider import AuthorizationCode, RefreshToken
from mcp.server.auth.handlers.token import OAuthToken
from src.config.settings import settings
from src.services.auth.oauth_storage import oauth_storage
from src.utils.logger import get_logger
from urllib.parse import urlparse, urlunparse
from pydantic import AnyUrl

logger = get_logger(__name__)


class ApiKeyVerifier(TokenVerifier):
    def __init__(self, base_url: str = None):
        super().__init__(base_url=base_url)
        self._valid_api_keys = self._load_valid_api_keys()

    def _load_valid_api_keys(self) -> set:
        api_keys = []
        if settings.MCP_AUTH_API_KEY:
            api_keys.append(settings.MCP_AUTH_API_KEY)
        if settings.MCP_AUTH_API_KEYS:
            api_keys.extend([k.strip() for k in settings.MCP_AUTH_API_KEYS.split(',') if k.strip()])
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


class FloodControlOAuthProvider(OAuthProvider):
    def __init__(self):
        super().__init__(
            base_url=settings.MCP_SERVER_BASE_URL,
            issuer_url=settings.MCP_SERVER_BASE_URL,
            required_scopes=["mcp_access"]
        )
        self._init_default_users()

    def _init_default_users(self):
        default_users = settings.MCP_OAUTH_USERS
        if default_users:
            for user_str in default_users.split(','):
                user_str = user_str.strip()
                if ':' in user_str:
                    username, password = user_str.split(':', 1)
                    oauth_storage.create_user(username, password, ["mcp_access"])

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        client_data = oauth_storage.get_client(client_id)
        if client_data:
            return OAuthClientInformationFull(**client_data)
        return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        oauth_storage.register_client(client_info.dict())

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        redirect_uri = str(params.redirect_uri)
        state = params.state or ""
        
        code = oauth_storage.create_authorization_code(
            client_id=client.client_id,
            scopes=params.scopes or ["mcp_access"],
            redirect_uri=redirect_uri,
            code_challenge=params.code_challenge,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly
        )
        
        parsed = urlparse(redirect_uri)
        query_parts = []
        if parsed.query:
            query_parts.append(parsed.query)
        query_parts.append(f"code={code}")
        if state:
            query_parts.append(f"state={state}")
        
        new_query = '&'.join(query_parts)
        new_url = urlunparse(parsed._replace(query=new_query))
        
        logger.info(f"Authorization code issued for client {client.client_id}")
        return new_url

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> AuthorizationCode | None:
        auth_code_data = oauth_storage.get_authorization_code(authorization_code)
        if not auth_code_data:
            return None
        
        return AuthorizationCode(
            code=auth_code_data['code'],
            scopes=auth_code_data['scopes'],
            expires_at=auth_code_data['expires_at'],
            client_id=auth_code_data['client_id'],
            code_challenge=auth_code_data['code_challenge'],
            redirect_uri=AnyUrl(auth_code_data['redirect_uri']),
            redirect_uri_provided_explicitly=auth_code_data['redirect_uri_provided_explicitly']
        )

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        oauth_storage.mark_code_used(authorization_code.code)
        
        tokens = oauth_storage.create_tokens(
            client_id=client.client_id,
            scopes=authorization_code.scopes
        )
        
        logger.info(f"Tokens issued for client {client.client_id}")
        return OAuthToken(
            access_token=tokens['access_token'],
            token_type='Bearer',
            expires_in=tokens['expires_in'],
            scope=' '.join(authorization_code.scopes),
            refresh_token=tokens['refresh_token']
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        token_data = oauth_storage.get_refresh_token(refresh_token)
        if not token_data:
            return None
        
        return RefreshToken(
            token=token_data['token'],
            client_id=token_data['client_id'],
            scopes=token_data['scopes'],
            expires_at=int(token_data['expires_at']) if token_data.get('expires_at') else None
        )

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        new_tokens = oauth_storage.create_tokens(
            client_id=client.client_id,
            scopes=scopes or refresh_token.scopes
        )
        
        oauth_storage.revoke_token(refresh_token.token, 'refresh')
        
        logger.info(f"Refresh token exchanged for client {client.client_id}")
        return OAuthToken(
            access_token=new_tokens['access_token'],
            token_type='Bearer',
            expires_in=new_tokens['expires_in'],
            scope=' '.join(scopes or refresh_token.scopes),
            refresh_token=new_tokens['refresh_token']
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        token_data = oauth_storage.get_access_token(token)
        if not token_data:
            return None
        
        return AccessToken(
            token=token_data['token'],
            client_id=token_data['client_id'],
            scopes=token_data['scopes'],
            expires_at=int(token_data['expires_at']) if token_data['expires_at'] else None,
            claims={"client_id": token_data['client_id']}
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            oauth_storage.revoke_token(token.token, 'access')
        elif isinstance(token, RefreshToken):
            oauth_storage.revoke_token(token.token, 'refresh')

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.load_access_token(token)