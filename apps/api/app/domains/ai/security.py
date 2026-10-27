"""Outbound-URL guard for user-supplied ``base_url`` values (SSRF hardening).

The AI endpoints accept a ``base_url`` from the client so users can bring their
own provider. Without validation that turns the local API into an open proxy:
any authenticated caller could make the server call internal services or a cloud
metadata endpoint.

Rules, in order:

1. scheme must be ``http`` or ``https``;
2. the host must resolve (IP literals are used directly);
3. link-local / cloud-metadata targets are *always* rejected;
4. loopback / RFC1918 / otherwise non-global targets are rejected unless
   ``CAREERPILOT_AI_ALLOW_PRIVATE_HOSTS`` is true (default, for local Ollama).

Resolution failures are rejected rather than allowed, because "cannot verify"
is exactly the case an attacker would aim for.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import get_settings

BLOCKED_HOSTNAMES = {
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
}
BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
    ipaddress.ip_address("100.100.100.200"),
}
ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}


class BaseUrlRejected(ValueError):
    """Raised with a user-facing reason when a base_url must not be called."""


def validate_base_url(value: str) -> str:
    """Return a normalised base_url or raise :class:`BaseUrlRejected`."""

    raw = (value or "").strip()
    if not raw:
        raise BaseUrlRejected("base_url 不能为空")

    parts = urlsplit(raw)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise BaseUrlRejected("base_url 必须以 http:// 或 https:// 开头")
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise BaseUrlRejected("base_url 缺少主机名")
    if host in BLOCKED_HOSTNAMES:
        raise BaseUrlRejected("不允许把云厂商元数据地址作为 base_url")

    try:
        port = parts.port or DEFAULT_PORTS[parts.scheme.lower()]
    except ValueError as exc:  # invalid port in the URL
        raise BaseUrlRejected("base_url 的端口不合法") from exc

    addresses = _resolve(host, port)
    if not addresses:
        raise BaseUrlRejected("base_url 的域名无法解析，请检查地址是否正确")

    settings = get_settings()
    for address in addresses:
        if address in BLOCKED_IPS:
            raise BaseUrlRejected("不允许把云厂商元数据地址作为 base_url")
        if not address.is_global:
            if settings.ai_allow_private_hosts:
                continue
            raise BaseUrlRejected(
                "当前部署禁止访问内网/本机地址；如确需本地模型，"
                "请由管理员设置 CAREERPILOT_AI_ALLOW_PRIVATE_HOSTS=true"
            )

    return raw.rstrip("/")


def _resolve(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if address not in addresses:
            addresses.append(address)
    return addresses
