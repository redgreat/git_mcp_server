"""
管理后台认证服务
"""
import time
import hmac
import hashlib
import jwt
import bcrypt
from sqlalchemy import Table, MetaData, select, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from fastapi import HTTPException


class AuthService:
    """认证服务"""

    def __init__(self, master_key: str, jwt_secret: str, session_timeout: int = 3600):
        self.master_key = master_key
        self.jwt_secret = jwt_secret
        self.session_timeout = session_timeout

    def hash_password(self, password: str) -> str:
        """生成密码哈希"""
        peppered = hmac.new(
            self.master_key.encode('utf-8'),
            password.encode('utf-8'),
            hashlib.sha256
        ).digest()
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(peppered, salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        peppered = hmac.new(
            self.master_key.encode('utf-8'),
            password.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return bcrypt.checkpw(peppered, password_hash.encode('utf-8'))

    def login(self, engine: Engine, username: str, password: str) -> dict:
        """用户登录，返回 JWT token"""
        meta = MetaData()
        admin_users = Table("admin_users", meta, autoload_with=engine)

        with Session(engine) as session:
            user = session.execute(
                select(admin_users).where(
                    admin_users.c.username == username,
                    admin_users.c.is_active == True  # noqa: E712
                )
            ).mappings().first()

            if not user:
                raise HTTPException(status_code=401, detail="用户名或密码错误")

            if not self.verify_password(password, user['password_hash']):
                raise HTTPException(status_code=401, detail="用户名或密码错误")

            now = int(time.time())
            token = jwt.encode(
                {
                    "sub": str(user['id']),
                    "username": user['username'],
                    "role": user['role'],
                    "iat": now,
                    "exp": now + self.session_timeout,
                },
                self.jwt_secret,
                algorithm="HS256"
            )

            return {
                "token": token,
                "username": user['username'],
                "role": user['role'],
            }

    def verify_token(self, token: str) -> dict:
        """验证 JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token 已过期")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="无效的 Token")

    def require_admin(self, token_payload: dict):
        """要求管理员权限"""
        if token_payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")
