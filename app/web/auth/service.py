"""密码哈希 + JWT 签发/验证服务。"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt as pyjwt

from app.config import config


def hash_password(plain: str) -> str:
    """将明文密码哈希为 bcrypt 字符串。"""
    return bcrypt.hashpw(
        plain.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(
        plain.encode("utf-8"), hashed.encode("utf-8")
    )


def create_access_token(user_id: int, username: str) -> str:
    """签发 JWT access token。"""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": now + timedelta(hours=config.web.jwt_expire_hours),
        "iat": now,
    }
    return pyjwt.encode(
        payload,
        config.web.jwt_secret_key,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """解码并校验 JWT。无效时抛 pyjwt.PyJWTError。"""
    return pyjwt.decode(
        token,
        config.web.jwt_secret_key,
        algorithms=["HS256"],
    )
