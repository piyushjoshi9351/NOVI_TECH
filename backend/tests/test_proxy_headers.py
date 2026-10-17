"""Forwarded client IPs require explicit proxy trust, including loopback."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import Settings
from app.core.rate_limit import IpRateLimiter


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1", "203.0.113.2"])
def test_default_proxy_trust_is_empty_and_forwarded_ip_cannot_bypass_limit(monkeypatch, peer):
    monkeypatch.delenv("TRUSTED_PROXY_HOSTS", raising=False)
    config = Settings(_env_file=None)
    assert config.TRUSTED_PROXY_HOSTS == ""
    app = FastAPI()
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=[host.strip() for host in config.TRUSTED_PROXY_HOSTS.split(",") if host.strip()])
    limiter = IpRateLimiter(limit=1)

    @app.get("/peer")
    def address(request: Request):
        limiter(request)
        return {"ip": request.client.host, "scheme": request.url.scheme}

    client = TestClient(app, client=(peer, 1000))
    response = client.get("/peer", headers={"X-Forwarded-For": "198.51.100.1", "X-Forwarded-Proto": "https"})
    assert response.json() == {"ip": peer, "scheme": "http"}
    assert client.get("/peer", headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 429
