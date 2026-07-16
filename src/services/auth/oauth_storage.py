import os
import json
import time
import secrets
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from src.utils.logger import get_logger
from src.services.storage.database.connection import get_db

logger = get_logger(__name__)


class OAuthStorage:
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'oauth')
        self._storage_dir = storage_dir

        self._db = get_db()
        self._ensure_tables()
        self._migrate_from_json()

    def _ensure_tables(self):
        """确保 OAuth 相关表存在"""
        tables = [
            'oauth_users', 'oauth_clients', 'oauth_auth_codes',
            'oauth_access_tokens', 'oauth_refresh_tokens'
        ]
        existing = [row['name'] for row in self._db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
        for table in tables:
            if table not in existing:
                create_sql_map = {
                    'oauth_users': """
                        CREATE TABLE IF NOT EXISTS oauth_users (
                            username TEXT PRIMARY KEY,
                            password_hash TEXT NOT NULL,
                            scopes TEXT NOT NULL DEFAULT '[]',
                            created_at REAL NOT NULL
                        )
                    """,
                    'oauth_clients': """
                        CREATE TABLE IF NOT EXISTS oauth_clients (
                            client_id TEXT PRIMARY KEY,
                            client_name TEXT,
                            client_secret TEXT,
                            redirect_uris TEXT NOT NULL DEFAULT '[]',
                            scopes TEXT NOT NULL DEFAULT '[]',
                            created_at REAL NOT NULL
                        )
                    """,
                    'oauth_auth_codes': """
                        CREATE TABLE IF NOT EXISTS oauth_auth_codes (
                            code TEXT PRIMARY KEY,
                            client_id TEXT NOT NULL,
                            scopes TEXT NOT NULL DEFAULT '[]',
                            expires_at REAL NOT NULL,
                            code_challenge TEXT,
                            redirect_uri TEXT,
                            redirect_uri_provided_explicitly INTEGER NOT NULL DEFAULT 0,
                            used INTEGER NOT NULL DEFAULT 0
                        )
                    """,
                    'oauth_access_tokens': """
                        CREATE TABLE IF NOT EXISTS oauth_access_tokens (
                            token TEXT PRIMARY KEY,
                            client_id TEXT NOT NULL,
                            scopes TEXT NOT NULL DEFAULT '[]',
                            expires_at REAL NOT NULL,
                            created_at REAL NOT NULL
                        )
                    """,
                    'oauth_refresh_tokens': """
                        CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
                            token TEXT PRIMARY KEY,
                            client_id TEXT NOT NULL,
                            scopes TEXT NOT NULL DEFAULT '[]',
                            expires_at REAL NOT NULL
                        )
                    """,
                }
                self._db.execute_script(create_sql_map[table])
                logger.info(f"Created table: {table}")

    def _migrate_from_json(self):
        """从 JSON 文件自动迁移到 SQLite（仅执行一次）"""
        # 检查 SQLite 是否已有数据
        user_count = self._db.execute_one("SELECT COUNT(*) as cnt FROM oauth_users")['cnt']
        if user_count > 0:
            return  # 已有数据，跳过迁移

        # 检查 JSON 文件是否存在
        users_file = os.path.join(self._storage_dir, 'users.json')
        if not os.path.exists(users_file):
            return  # 无旧数据，跳过

        logger.info("检测到旧版 JSON OAuth 数据，开始自动迁移到 SQLite...")

        # 迁移用户数据
        users_data = self._load_json(users_file)
        for username, user_info in users_data.items():
            self._db.execute_insert(
                "INSERT OR IGNORE INTO oauth_users (username, password_hash, scopes, created_at) VALUES (?, ?, ?, ?)",
                (user_info['username'], user_info['password_hash'],
                 json.dumps(user_info.get('scopes', [])), user_info['created_at'])
            )
        logger.info(f"迁移用户数据: {len(users_data)} 条")

        # 迁移客户端数据
        clients_file = os.path.join(self._storage_dir, 'clients.json')
        clients_data = self._load_json(clients_file)
        for client_id, client_info in clients_data.items():
            self._db.execute_insert(
                "INSERT OR IGNORE INTO oauth_clients (client_id, client_name, client_secret, redirect_uris, scopes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (client_info['client_id'],
                 client_info.get('client_name'),
                 client_info.get('client_secret'),
                 json.dumps(client_info.get('redirect_uris', [])),
                 json.dumps(client_info.get('scopes', [])),
                 client_info.get('created_at', time.time()))
            )
        logger.info(f"迁移客户端数据: {len(clients_data)} 条")

        # 迁移授权码数据
        auth_codes_file = os.path.join(self._storage_dir, 'auth_codes.json')
        auth_codes_data = self._load_json(auth_codes_file)
        for code, code_info in auth_codes_data.items():
            self._db.execute_insert(
                "INSERT OR IGNORE INTO oauth_auth_codes (code, client_id, scopes, expires_at, code_challenge, redirect_uri, redirect_uri_provided_explicitly, used) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (code_info['code'], code_info['client_id'],
                 json.dumps(code_info.get('scopes', [])),
                 code_info['expires_at'],
                 code_info.get('code_challenge'),
                 code_info.get('redirect_uri'),
                 1 if code_info.get('redirect_uri_provided_explicitly', False) else 0,
                 1 if code_info.get('used', False) else 0)
            )
        logger.info(f"迁移授权码数据: {len(auth_codes_data)} 条")

        # 迁移访问令牌数据
        access_tokens_file = os.path.join(self._storage_dir, 'access_tokens.json')
        access_tokens_data = self._load_json(access_tokens_file)
        for token, token_info in access_tokens_data.items():
            self._db.execute_insert(
                "INSERT OR IGNORE INTO oauth_access_tokens (token, client_id, scopes, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (token_info['token'], token_info['client_id'],
                 json.dumps(token_info.get('scopes', [])),
                 token_info['expires_at'],
                 token_info.get('created_at', time.time()))
            )
        logger.info(f"迁移访问令牌数据: {len(access_tokens_data)} 条")

        # 迁移刷新令牌数据
        refresh_tokens_file = os.path.join(self._storage_dir, 'refresh_tokens.json')
        refresh_tokens_data = self._load_json(refresh_tokens_file)
        for token, token_info in refresh_tokens_data.items():
            self._db.execute_insert(
                "INSERT OR IGNORE INTO oauth_refresh_tokens (token, client_id, scopes, expires_at) VALUES (?, ?, ?, ?)",
                (token_info['token'], token_info['client_id'],
                 json.dumps(token_info.get('scopes', [])),
                 token_info['expires_at'])
            )
        logger.info(f"迁移刷新令牌数据: {len(refresh_tokens_data)} 条")

        logger.info("OAuth JSON 数据迁移到 SQLite 完成（旧 JSON 文件已保留作为备份）")

    def _load_json(self, file_path: str) -> dict:
        """从 JSON 文件加载数据（保留用于迁移回退）"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
        return {}

    def _save_json(self, file_path: str, data: dict):
        """保存数据到 JSON 文件（保留用于迁移回退）"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {file_path}: {e}")

    def create_user(self, username: str, password: str, scopes: List[str] = None) -> bool:
        hashed = self._hash_password(password)
        self._db.execute_insert(
            "INSERT OR IGNORE INTO oauth_users (username, password_hash, scopes, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed, json.dumps(scopes or []), time.time())
        )
        logger.info(f"Created user: {username}")
        return True

    def verify_user(self, username: str, password: str) -> Optional[dict]:
        row = self._db.execute_one("SELECT * FROM oauth_users WHERE username = ?", (username,))
        if not row:
            return None
        if self._verify_password(password, row['password_hash']):
            return {
                'username': row['username'],
                'password_hash': row['password_hash'],
                'scopes': json.loads(row['scopes']),
                'created_at': row['created_at']
            }
        return None

    def _hash_password(self, password: str) -> str:
        try:
            from passlib.hash import bcrypt
            return bcrypt.hash(password)
        except ImportError:
            import hashlib
            logger.warning("passlib 未安装，使用 SHA-256 作为备用。请运行: uv add passlib[bcrypt]")
            return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, hash: str) -> bool:
        try:
            from passlib.hash import bcrypt
            # bcrypt 哈希以 $2b$ 开头，兼容旧版 SHA-256
            if hash.startswith('$2b$') or hash.startswith('$2a$') or hash.startswith('$2y$'):
                return bcrypt.verify(password, hash)
            else:
                import hashlib
                return hashlib.sha256(password.encode()).hexdigest() == hash
        except ImportError:
            import hashlib
            return hashlib.sha256(password.encode()).hexdigest() == hash

    def register_client(self, client_info: dict) -> None:
        self._db.execute_insert(
            "INSERT OR REPLACE INTO oauth_clients (client_id, client_name, client_secret, redirect_uris, scopes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (client_info['client_id'],
             client_info.get('client_name'),
             client_info.get('client_secret'),
             json.dumps(client_info.get('redirect_uris', [])),
             json.dumps(client_info.get('scopes', [])),
             client_info.get('created_at', time.time()))
        )
        logger.info(f"Registered client: {client_info['client_id']}")

    def get_client(self, client_id: str) -> Optional[dict]:
        row = self._db.execute_one("SELECT * FROM oauth_clients WHERE client_id = ?", (client_id,))
        if not row:
            return None
        return {
            'client_id': row['client_id'],
            'client_name': row.get('client_name'),
            'client_secret': row.get('client_secret'),
            'redirect_uris': json.loads(row['redirect_uris']),
            'scopes': json.loads(row['scopes']),
            'created_at': row['created_at']
        }

    def create_authorization_code(self, client_id: str, scopes: List[str],
                                   redirect_uri: str, code_challenge: str,
                                   redirect_uri_provided_explicitly: bool) -> str:
        code = secrets.token_urlsafe(32)
        now = time.time()
        self._db.execute_insert(
            "INSERT INTO oauth_auth_codes (code, client_id, scopes, expires_at, code_challenge, redirect_uri, redirect_uri_provided_explicitly, used) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (code, client_id, json.dumps(scopes), now + 300,
             code_challenge, redirect_uri,
             1 if redirect_uri_provided_explicitly else 0, 0)
        )
        return code

    def get_authorization_code(self, code: str) -> Optional[dict]:
        row = self._db.execute_one("SELECT * FROM oauth_auth_codes WHERE code = ?", (code,))
        if not row:
            return None
        if time.time() > row['expires_at']:
            self._db.execute_update("DELETE FROM oauth_auth_codes WHERE code = ?", (code,))
            return None
        if row['used']:
            return None
        return {
            'code': row['code'],
            'client_id': row['client_id'],
            'scopes': json.loads(row['scopes']),
            'expires_at': row['expires_at'],
            'code_challenge': row.get('code_challenge'),
            'redirect_uri': row.get('redirect_uri'),
            'redirect_uri_provided_explicitly': bool(row['redirect_uri_provided_explicitly']),
            'used': bool(row['used'])
        }

    def mark_code_used(self, code: str):
        self._db.execute_update(
            "UPDATE oauth_auth_codes SET used = 1 WHERE code = ?", (code,)
        )

    def create_tokens(self, client_id: str, scopes: List[str]) -> dict:
        access_token = secrets.token_urlsafe(48)
        refresh_token = secrets.token_urlsafe(64)
        now = time.time()

        self._db.execute_insert(
            "INSERT INTO oauth_access_tokens (token, client_id, scopes, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (access_token, client_id, json.dumps(scopes), now + 3600, now)
        )

        self._db.execute_insert(
            "INSERT INTO oauth_refresh_tokens (token, client_id, scopes, expires_at) VALUES (?, ?, ?, ?)",
            (refresh_token, client_id, json.dumps(scopes), now + 7 * 24 * 3600)
        )

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 3600
        }

    def get_access_token(self, token: str) -> Optional[dict]:
        row = self._db.execute_one("SELECT * FROM oauth_access_tokens WHERE token = ?", (token,))
        if not row:
            return None
        if time.time() > row['expires_at']:
            self._db.execute_update("DELETE FROM oauth_access_tokens WHERE token = ?", (token,))
            return None
        return {
            'token': row['token'],
            'client_id': row['client_id'],
            'scopes': json.loads(row['scopes']),
            'expires_at': row['expires_at'],
            'created_at': row['created_at']
        }

    def get_refresh_token(self, token: str) -> Optional[dict]:
        row = self._db.execute_one("SELECT * FROM oauth_refresh_tokens WHERE token = ?", (token,))
        if not row:
            return None
        if time.time() > row['expires_at']:
            self._db.execute_update("DELETE FROM oauth_refresh_tokens WHERE token = ?", (token,))
            return None
        return {
            'token': row['token'],
            'client_id': row['client_id'],
            'scopes': json.loads(row['scopes']),
            'expires_at': row['expires_at']
        }

    def revoke_token(self, token: str, token_type: str = 'access'):
        if token_type == 'access':
            self._db.execute_update("DELETE FROM oauth_access_tokens WHERE token = ?", (token,))
        elif token_type == 'refresh':
            self._db.execute_update("DELETE FROM oauth_refresh_tokens WHERE token = ?", (token,))
        logger.info(f"Revoked {token_type} token")

    def cleanup_expired_tokens(self):
        now = time.time()

        access_deleted = self._db.execute_update(
            "DELETE FROM oauth_access_tokens WHERE expires_at < ?", (now,)
        )
        refresh_deleted = self._db.execute_update(
            "DELETE FROM oauth_refresh_tokens WHERE expires_at < ?", (now,)
        )

        if access_deleted or refresh_deleted:
            logger.info(
                f"Cleaned up {access_deleted} access tokens and {refresh_deleted} refresh tokens"
            )


oauth_storage = OAuthStorage()
