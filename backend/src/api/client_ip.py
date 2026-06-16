from __future__ import annotations

import ipaddress

from fastapi import Request

from ..config import app_config


def _request_host(request: Request) -> str:
    try:
        host = request.client.host if request.client else ""
    except Exception:
        host = ""
    value = str(host or "").strip()
    return value or "unknown"


def _valid_ip(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return str(ipaddress.ip_address(text))
    except Exception:
        return None


def _proxy_is_trusted(remote_ip: str, trusted_proxy_ips: list[str]) -> bool:
    if not trusted_proxy_ips:
        return False
    remote = _valid_ip(remote_ip)
    if not remote:
        return False
    for item in trusted_proxy_ips:
        raw = str(item or "").strip()
        if not raw:
            continue
        if raw == "*":
            return True
        try:
            if "/" in raw:
                if ipaddress.ip_address(remote) in ipaddress.ip_network(raw, strict=False):
                    return True
            elif remote == str(ipaddress.ip_address(raw)):
                return True
        except Exception:
            continue
    return False


def resolve_client_ip(
    request: Request,
    *,
    trust_proxy: bool | None = None,
    trusted_proxy_ips: list[str] | None = None,
) -> str:
    cfg = app_config()
    should_trust_proxy = bool(cfg.trust_proxy if trust_proxy is None else trust_proxy)
    allowed_proxies = list(cfg.trusted_proxy_ips if trusted_proxy_ips is None else trusted_proxy_ips)
    remote_ip = _request_host(request)
    if not should_trust_proxy:
        return remote_ip
    if not _proxy_is_trusted(remote_ip, allowed_proxies):
        return remote_ip

    raw_xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For") or ""
    for part in str(raw_xff).split(","):
        candidate = _valid_ip(part)
        if candidate:
            return candidate
    return remote_ip
