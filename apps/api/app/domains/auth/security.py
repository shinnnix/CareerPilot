import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(digest, _decode(expected))
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    token_version: int
    expires_at: int


def create_access_token(*, subject: str, token_version: int, secret: str, ttl_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": subject,
        "ver": token_version,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    signing_input = f"{_encode_json(header)}.{_encode_json(payload)}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{signing_input.decode('ascii')}.{_encode(signature)}"


def decode_access_token(token: str, *, secret: str) -> TokenClaims | None:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature_part)):
            return None
        header = json.loads(_decode(header_part))
        payload = json.loads(_decode(payload_part))
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        expires_at = int(payload["exp"])
        if expires_at <= int(time.time()):
            return None
        return TokenClaims(
            subject=str(payload["sub"]),
            token_version=int(payload["ver"]),
            expires_at=expires_at,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        return None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _encode_json(value: dict[str, object]) -> str:
    return _encode(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))
