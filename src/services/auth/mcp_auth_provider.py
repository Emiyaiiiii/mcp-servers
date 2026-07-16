from fastmcp.server.auth import OAuthProvider, TokenVerifier, AccessToken, JWTVerifier
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


class JWTTokenVerifier(TokenVerifier):
    """JWT 令牌验证器，支持三种验证模式 + 兼容 API Key 模式。

    验证模式（由 MCP_JWT_MODE 控制）:
      - jwks:       从 JWKS 端点获取公钥验证（支持自动密钥轮换）
      - public_key: 使用静态 RSA/ECDSA 公钥验证
      - hmac:       使用共享密钥（HMAC）验证
      - api_key:    兼容旧的简单 API Key 比对（默认）
    """

    def __init__(self, base_url: str = None):
        super().__init__(base_url=base_url)
        self._mode = settings.MCP_JWT_MODE
        self._valid_api_keys = self._load_valid_api_keys()
        self._jwt_verifier = self._build_jwt_verifier()

    def _load_valid_api_keys(self) -> set:
        keys = set()
        if settings.MCP_AUTH_API_KEY:
            keys.add(settings.MCP_AUTH_API_KEY)
        return keys

    def _build_jwt_verifier(self) -> JWTVerifier | None:
        """根据配置构建 JWTVerifier 实例"""
        if self._mode == "jwks":
            if not settings.MCP_JWKS_URI:
                logger.warning("JWT 模式为 jwks 但未配置 MCP_JWKS_URI")
                return None
            logger.info(f"JWT 验证器: JWKS 模式 — {settings.MCP_JWKS_URI}")
            return JWTVerifier(
                jwks_uri=settings.MCP_JWKS_URI,
                issuer=settings.MCP_JWT_ISSUER or None,
                audience=settings.MCP_JWT_AUDIENCE or None,
                algorithm=settings.MCP_JWT_ALGORITHM,
            )

        elif self._mode == "public_key":
            if not settings.MCP_JWT_PUBLIC_KEY:
                logger.warning("JWT 模式为 public_key 但未配置 MCP_JWT_PUBLIC_KEY")
                return None
            logger.info(f"JWT 验证器: 静态公钥模式 — 算法 {settings.MCP_JWT_ALGORITHM}")
            return JWTVerifier(
                public_key=settings.MCP_JWT_PUBLIC_KEY,
                algorithm=settings.MCP_JWT_ALGORITHM,
                issuer=settings.MCP_JWT_ISSUER or None,
                audience=settings.MCP_JWT_AUDIENCE or None,
            )

        elif self._mode == "hmac":
            if not settings.MCP_JWT_SECRET:
                logger.warning("JWT 模式为 hmac 但未配置 MCP_JWT_SECRET")
                return None
            algo = settings.MCP_JWT_ALGORITHM
            if algo not in ("HS256", "HS384", "HS512"):
                algo = "HS256"
                logger.warning(f"HMAC 模式不支持算法 {settings.MCP_JWT_ALGORITHM}，降级为 HS256")
            logger.info(f"JWT 验证器: HMAC 模式 — 算法 {algo}")
            return JWTVerifier(
                public_key=settings.MCP_JWT_SECRET,
                algorithm=algo,
                issuer=settings.MCP_JWT_ISSUER or None,
                audience=settings.MCP_JWT_AUDIENCE or None,
            )

        else:
            # api_key 模式 — 不使用 JWTVerifier
            logger.info(f"令牌验证器: API Key 模式（{len(self._valid_api_keys)} 个密钥）")
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            logger.warning("空令牌")
            return None

        # JWT 模式 — 委托给 JWTVerifier
        if self._jwt_verifier is not None:
            try:
                result = await self._jwt_verifier.verify_token(token)
                if result:
                    logger.info("JWT 令牌验证成功")
                else:
                    logger.warning("JWT 令牌验证失败")
                return result
            except Exception as e:
                logger.warning(f"JWT 令牌验证异常: {e}")
                return None

        # API Key 模式 — 简单比对
        if token in self._valid_api_keys:
            logger.info("API Key 验证成功")
            return AccessToken(
                token=token,
                client_id="mcp_client",
                scopes=["data"],
                expires_at=None,
                claims={"role": "mcp_user"},
            )

        logger.warning("API Key 验证失败")
        return None


class FloodControlOAuthProvider(OAuthProvider):
    def __init__(self):
        super().__init__(
            base_url=settings.MCP_SERVER_BASE_URL,
            issuer_url=settings.MCP_SERVER_BASE_URL,
            required_scopes=["data"]
        )
        self._init_default_users()

    def _init_default_users(self):
        default_users = settings.MCP_OAUTH_USERS
        if default_users:
            for user_str in default_users.split(','):
                user_str = user_str.strip()
                if ':' in user_str:
                    username, password = user_str.split(':', 1)
                    oauth_storage.create_user(username, password, ["data"])

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
            scopes=params.scopes or ["data"],
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