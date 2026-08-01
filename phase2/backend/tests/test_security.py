"""security.py 纯函数单元测试（不依赖数据库）。"""

from datetime import timedelta

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHash:
    def test_hash_and_verify_roundtrip(self):
        hashed = hash_password("admin123456")
        assert hashed != "admin123456"
        assert verify_password("admin123456", hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_hash_is_salted(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2


class TestJWT:
    def test_access_token_roundtrip(self):
        token = create_access_token(42)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        token = create_refresh_token(42)
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        assert decode_token("not-a-jwt") is None
        assert decode_token("") is None

    def test_decode_expired_token(self):
        token = create_access_token(42, expires_delta=timedelta(seconds=-10))
        assert decode_token(token) is None

    def test_decode_after_modification_fails(self):
        token = create_access_token(42)
        payload = decode_token(token)
        assert payload is not None
        # 篡改 payload 后签名失效
        assert decode_token(token[:-1] + ("A" if token[-1] != "A" else "B")) is None
