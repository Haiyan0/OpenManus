"""认证服务：密码哈希与 JWT。"""
import pytest

from app.web.auth.service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    """密码哈希后可正确验证。"""
    plain = "my_secret_password"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_roundtrip():
    """JWT 签发后可解码。"""
    token = create_access_token(user_id=42, username="alice")
    payload = decode_access_token(token)
    assert payload["user_id"] == 42
    assert payload["username"] == "alice"
    assert "exp" in payload


def test_invalid_token_raises():
    """无效 token 应抛 jwt 异常。"""
    import jwt as pyjwt

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token("not.a.valid.token")
