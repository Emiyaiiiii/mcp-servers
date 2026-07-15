import os
import json
import time
import secrets
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OAuthStorage:
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'oauth')
        self._storage_dir = storage_dir
        os.makedirs(self._storage_dir, exist_ok=True)
        
        self._users_file = os.path.join(self._storage_dir, 'users.json')
        self._clients_file = os.path.join(self._storage_dir, 'clients.json')
        self._auth_codes_file = os.path.join(self._storage_dir, 'auth_codes.json')
        self._refresh_tokens_file = os.path.join(self._storage_dir, 'refresh_tokens.json')
        self._access_tokens_file = os.path.join(self._storage_dir, 'access_tokens.json')
        
        self._load_data()

    def _load_data(self):
        self._users: Dict[str, dict] = self._load_json(self._users_file)
        self._clients: Dict[str, dict] = self._load_json(self._clients_file)
        self._auth_codes: Dict[str, dict] = self._load_json(self._auth_codes_file)
        self._refresh_tokens: Dict[str, dict] = self._load_json(self._refresh_tokens_file)
        self._access_tokens: Dict[str, dict] = self._load_json(self._access_tokens_file)

    def _load_json(self, file_path: str) -> dict:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
        return {}

    def _save_json(self, file_path: str, data: dict):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {file_path}: {e}")

    def _save_all(self):
        self._save_json(self._users_file, self._users)
        self._save_json(self._clients_file, self._clients)
        self._save_json(self._auth_codes_file, self._auth_codes)
        self._save_json(self._refresh_tokens_file, self._refresh_tokens)
        self._save_json(self._access_tokens_file, self._access_tokens)

    def create_user(self, username: str, password: str, scopes: List[str] = None) -> bool:
        if username in self._users:
            return False
        hashed_password = self._hash_password(password)
        self._users[username] = {
            'username': username,
            'password_hash': hashed_password,
            'scopes': scopes or [],
            'created_at': time.time()
        }
        self._save_all()
        logger.info(f"Created user: {username}")
        return True

    def verify_user(self, username: str, password: str) -> Optional[dict]:
        user = self._users.get(username)
        if not user:
            return None
        if self._verify_password(password, user['password_hash']):
            return user
        return None

    def _hash_password(self, password: str) -> str:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

    def _verify_password(self, password: str, hash: str) -> bool:
        return self._hash_password(password) == hash

    def register_client(self, client_info: dict) -> None:
        client_id = client_info['client_id']
        self._clients[client_id] = client_info
        self._save_all()
        logger.info(f"Registered client: {client_id}")

    def get_client(self, client_id: str) -> Optional[dict]:
        return self._clients.get(client_id)

    def create_authorization_code(self, client_id: str, scopes: List[str], 
                                   redirect_uri: str, code_challenge: str,
                                   redirect_uri_provided_explicitly: bool) -> str:
        code = secrets.token_urlsafe(32)
        now = time.time()
        self._auth_codes[code] = {
            'code': code,
            'client_id': client_id,
            'scopes': scopes,
            'expires_at': now + 300,
            'code_challenge': code_challenge,
            'redirect_uri': redirect_uri,
            'redirect_uri_provided_explicitly': redirect_uri_provided_explicitly,
            'used': False
        }
        self._save_all()
        return code

    def get_authorization_code(self, code: str) -> Optional[dict]:
        auth_code = self._auth_codes.get(code)
        if not auth_code:
            return None
        if time.time() > auth_code['expires_at']:
            del self._auth_codes[code]
            self._save_all()
            return None
        if auth_code['used']:
            return None
        return auth_code

    def mark_code_used(self, code: str):
        if code in self._auth_codes:
            self._auth_codes[code]['used'] = True
            self._save_all()

    def create_tokens(self, client_id: str, scopes: List[str]) -> dict:
        access_token = secrets.token_urlsafe(48)
        refresh_token = secrets.token_urlsafe(64)
        now = time.time()
        
        self._access_tokens[access_token] = {
            'token': access_token,
            'client_id': client_id,
            'scopes': scopes,
            'expires_at': now + 3600,
            'created_at': now
        }
        
        self._refresh_tokens[refresh_token] = {
            'token': refresh_token,
            'client_id': client_id,
            'scopes': scopes,
            'expires_at': now + 7 * 24 * 3600
        }
        
        self._save_all()
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': 3600
        }

    def get_access_token(self, token: str) -> Optional[dict]:
        access_token = self._access_tokens.get(token)
        if not access_token:
            return None
        if time.time() > access_token['expires_at']:
            del self._access_tokens[token]
            self._save_all()
            return None
        return access_token

    def get_refresh_token(self, token: str) -> Optional[dict]:
        refresh_token = self._refresh_tokens.get(token)
        if not refresh_token:
            return None
        if time.time() > refresh_token['expires_at']:
            del self._refresh_tokens[token]
            self._save_all()
            return None
        return refresh_token

    def revoke_token(self, token: str, token_type: str = 'access'):
        if token_type == 'access' and token in self._access_tokens:
            del self._access_tokens[token]
        elif token_type == 'refresh' and token in self._refresh_tokens:
            del self._refresh_tokens[token]
        self._save_all()
        logger.info(f"Revoked {token_type} token")

    def cleanup_expired_tokens(self):
        now = time.time()
        expired_access = [t for t, v in self._access_tokens.items() if v['expires_at'] < now]
        expired_refresh = [t for t, v in self._refresh_tokens.items() if v['expires_at'] < now]
        
        for t in expired_access:
            del self._access_tokens[t]
        for t in expired_refresh:
            del self._refresh_tokens[t]
        
        if expired_access or expired_refresh:
            self._save_all()
            logger.info(f"Cleaned up {len(expired_access)} access tokens and {len(expired_refresh)} refresh tokens")


oauth_storage = OAuthStorage()