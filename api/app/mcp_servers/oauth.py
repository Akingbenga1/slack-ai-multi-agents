"""MCP Connect/OAuth adapter — discover, PKCE authorize, store, refresh.

Plugs in at the credential boundary for remote HTTP MCP servers.
Does not hardcode a vendor; uses Protected Resource Metadata + OAuth 2.1 PKCE.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from api.app.db.models import McpServer
from api.app.db.tool_store import get_mcp_server
from api.app.logging_config import get_logger
from api.app.settings import Settings
from api.app.slack.crypto import decrypt_bot_token, encrypt_bot_token

logger = get_logger("api.mcp_servers.oauth")


class McpOAuthError(Exception):
    def __init__(self, message: str, *, code: str = "mcp_oauth_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class McpOAuthStart:
    server_id: str
    authorization_url: str
    state: str


def _redirect_uri(settings: Settings) -> str:
    base = (settings.public_base_url or "").rstrip("/")
    path = (settings.mcp_oauth_redirect_path or "/mcp-servers/oauth/callback").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    if not base:
        raise McpOAuthError("public_base_url is required for MCP Connect", code="misconfigured")
    return f"{base}{path}"


def _pkce_pair() -> tuple[str, str]:
    import base64

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _load_bundle(row: McpServer, settings: Settings) -> dict[str, Any]:
    raw = row.oauth_secret_encrypted
    if not raw:
        return {}
    try:
        plain = decrypt_bot_token(raw, settings)
        data = json.loads(plain)
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.warning("mcp_oauth_bundle_decrypt_failed server=%s", row.name)
        return {}


def _save_bundle(row: McpServer, bundle: dict[str, Any], settings: Settings) -> None:
    if not bundle:
        row.oauth_secret_encrypted = None
        return
    row.oauth_secret_encrypted = encrypt_bot_token(json.dumps(bundle), settings)


def oauth_connected(row: McpServer, settings: Settings) -> bool:
    bundle = _load_bundle(row, settings)
    tokens = bundle.get("tokens")
    return isinstance(tokens, dict) and bool(tokens.get("access_token") or tokens.get("refresh_token"))


def _well_known_urls(resource_url: str) -> list[str]:
    parsed = urlparse(resource_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    urls = [
        urljoin(origin + "/", ".well-known/oauth-protected-resource"),
    ]
    if path:
        urls.insert(
            0,
            urljoin(origin + "/", f".well-known/oauth-protected-resource{path}"),
        )
    return urls


def discover_resource_metadata(mcp_url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch Protected Resource Metadata for an MCP HTTP URL."""
    last_err: str | None = None
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        # Probe without auth — many servers return 401 + WWW-Authenticate.
        try:
            probe = client.get(mcp_url)
            www = probe.headers.get("www-authenticate") or probe.headers.get("WWW-Authenticate")
            if www and "resource_metadata=" in www:
                # resource_metadata="https://..."
                for part in www.split(","):
                    part = part.strip()
                    if "resource_metadata=" in part:
                        meta_url = part.split("resource_metadata=", 1)[1].strip().strip('"')
                        res = client.get(meta_url)
                        if res.status_code < 400:
                            data = res.json()
                            if isinstance(data, dict):
                                return data
        except Exception as exc:
            last_err = str(exc)

        for meta_url in _well_known_urls(mcp_url):
            try:
                res = client.get(meta_url)
                if res.status_code >= 400:
                    last_err = f"{meta_url} -> {res.status_code}"
                    continue
                data = res.json()
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                last_err = str(exc)
    raise McpOAuthError(
        f"could not discover protected resource metadata for {mcp_url!r}: {last_err}",
        code="discovery_failed",
    )


def discover_authorization_server(issuer: str, *, timeout: float = 20.0) -> dict[str, Any]:
    issuer = issuer.rstrip("/")
    candidates = [
        f"{issuer}/.well-known/oauth-authorization-server",
        f"{issuer}/.well-known/openid-configuration",
    ]
    last_err: str | None = None
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for url in candidates:
            try:
                res = client.get(url)
                if res.status_code >= 400:
                    last_err = f"{url} -> {res.status_code}"
                    continue
                data = res.json()
                if isinstance(data, dict) and data.get("authorization_endpoint"):
                    return data
            except Exception as exc:
                last_err = str(exc)
    raise McpOAuthError(
        f"could not discover authorization server metadata: {last_err}",
        code="discovery_failed",
    )


def start_mcp_oauth(
    db: Session,
    *,
    tenant_id: str | UUID,
    server_id: str | UUID,
    settings: Settings,
) -> McpOAuthStart:
    row = get_mcp_server(db, tenant_id=tenant_id, server_id=server_id)
    if row is None:
        raise McpOAuthError("mcp server not found", code="not_found")
    cfg = row.connection_config if isinstance(row.connection_config, dict) else {}
    mcp_url = str(cfg.get("url") or "").strip()
    if not mcp_url:
        raise McpOAuthError("mcp server has no URL", code="invalid_config")

    client_id = (settings.mcp_oauth_client_id or "").strip()
    if not client_id:
        raise McpOAuthError(
            "MCP_OAUTH_CLIENT_ID is required to Connect",
            code="misconfigured",
        )

    prm = discover_resource_metadata(mcp_url)
    auth_servers = prm.get("authorization_servers")
    if not isinstance(auth_servers, list) or not auth_servers:
        raise McpOAuthError(
            "protected resource metadata missing authorization_servers",
            code="discovery_failed",
        )
    issuer = str(auth_servers[0]).strip()
    as_meta = discover_authorization_server(issuer)
    auth_endpoint = str(as_meta.get("authorization_endpoint") or "").strip()
    token_endpoint = str(as_meta.get("token_endpoint") or "").strip()
    if not auth_endpoint or not token_endpoint:
        raise McpOAuthError("authorization server missing endpoints", code="discovery_failed")

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    redirect_uri = _redirect_uri(settings)
    scopes = (settings.mcp_oauth_scopes or "").strip()
    resource = str(prm.get("resource") or mcp_url).strip()

    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": resource,
    }
    if scopes:
        params["scope"] = scopes

    bundle = _load_bundle(row, settings)
    bundle["pending"] = {
        "state": state,
        "code_verifier": verifier,
        "token_endpoint": token_endpoint,
        "authorization_endpoint": auth_endpoint,
        "resource": resource,
        "redirect_uri": redirect_uri,
        "created_at": time.time(),
        "tenant_id": str(tenant_id),
        "server_id": str(row.id),
    }
    _save_bundle(row, bundle, settings)
    db.flush()

    url = f"{auth_endpoint}?{urlencode(params)}"
    logger.info("mcp_oauth_start server=%s", row.name)
    return McpOAuthStart(server_id=str(row.id), authorization_url=url, state=state)


def _find_row_by_pending_state(db: Session, state: str) -> McpServer | None:
    from sqlalchemy import select

    settings = Settings()
    rows = list(db.scalars(select(McpServer)).all())
    for row in rows:
        if not row.oauth_secret_encrypted:
            continue
        bundle = _load_bundle(row, settings)
        pending = bundle.get("pending")
        if isinstance(pending, dict) and pending.get("state") == state:
            return row
    return None


def complete_mcp_oauth(
    db: Session,
    *,
    state: str,
    code: str,
    settings: Settings,
) -> McpServer:
    row = _find_row_by_pending_state(db, state)
    if row is None:
        raise McpOAuthError("unknown or expired OAuth state", code="invalid_state")
    bundle = _load_bundle(row, settings)
    pending = bundle.get("pending")
    if not isinstance(pending, dict):
        raise McpOAuthError("missing OAuth pending state", code="invalid_state")

    token_endpoint = str(pending.get("token_endpoint") or "")
    verifier = str(pending.get("code_verifier") or "")
    redirect_uri = str(pending.get("redirect_uri") or _redirect_uri(settings))
    resource = str(pending.get("resource") or "")
    client_id = (settings.mcp_oauth_client_id or "").strip()
    client_secret = (settings.mcp_oauth_client_secret or "").strip()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if resource:
        data["resource"] = resource
    auth = (client_id, client_secret) if client_secret else None

    with httpx.Client(timeout=30.0) as client:
        res = client.post(token_endpoint, data=data, auth=auth)
        if res.status_code >= 400:
            raise McpOAuthError(
                f"token exchange failed: {res.status_code} {res.text[:300]}",
                code="token_exchange_failed",
            )
        payload = res.json()

    access = str(payload.get("access_token") or "").strip()
    if not access:
        raise McpOAuthError("token response missing access_token", code="token_exchange_failed")
    expires_in = payload.get("expires_in")
    expires_at = None
    if isinstance(expires_in, (int, float)):
        expires_at = time.time() + float(expires_in)

    bundle["tokens"] = {
        "access_token": access,
        "refresh_token": payload.get("refresh_token"),
        "expires_at": expires_at,
        "scope": payload.get("scope"),
        "token_type": payload.get("token_type") or "Bearer",
        "token_endpoint": token_endpoint,
        "resource": resource,
    }
    bundle.pop("pending", None)
    _save_bundle(row, bundle, settings)
    db.flush()
    logger.info("mcp_oauth_complete server=%s", row.name)
    return row


def refresh_mcp_oauth_access_token(
    row: McpServer,
    settings: Settings,
) -> str | None:
    bundle = _load_bundle(row, settings)
    tokens = bundle.get("tokens")
    if not isinstance(tokens, dict):
        return None
    refresh = str(tokens.get("refresh_token") or "").strip()
    token_endpoint = str(tokens.get("token_endpoint") or "").strip()
    if not refresh or not token_endpoint:
        return str(tokens.get("access_token") or "").strip() or None

    client_id = (settings.mcp_oauth_client_id or "").strip()
    client_secret = (settings.mcp_oauth_client_secret or "").strip()
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": client_id,
    }
    resource = str(tokens.get("resource") or "").strip()
    if resource:
        data["resource"] = resource
    auth = (client_id, client_secret) if client_secret else None
    with httpx.Client(timeout=30.0) as client:
        res = client.post(token_endpoint, data=data, auth=auth)
        if res.status_code >= 400:
            logger.warning(
                "mcp_oauth_refresh_failed server=%s status=%s",
                row.name,
                res.status_code,
            )
            return str(tokens.get("access_token") or "").strip() or None
        payload = res.json()
    access = str(payload.get("access_token") or "").strip()
    if not access:
        return str(tokens.get("access_token") or "").strip() or None
    expires_in = payload.get("expires_in")
    expires_at = time.time() + float(expires_in) if isinstance(expires_in, (int, float)) else None
    tokens["access_token"] = access
    if payload.get("refresh_token"):
        tokens["refresh_token"] = payload.get("refresh_token")
    tokens["expires_at"] = expires_at
    bundle["tokens"] = tokens
    _save_bundle(row, bundle, settings)
    return access


def access_token_for_mcp_server(
    row: McpServer,
    settings: Settings,
    *,
    service_token: str | None = None,
) -> str | None:
    """Prefer OAuth access token (refreshing when near expiry); else service token."""
    bundle = _load_bundle(row, settings)
    tokens = bundle.get("tokens")
    if isinstance(tokens, dict):
        expires_at = tokens.get("expires_at")
        access = str(tokens.get("access_token") or "").strip()
        near_expiry = isinstance(expires_at, (int, float)) and time.time() >= float(expires_at) - 60
        if near_expiry or not access:
            refreshed = refresh_mcp_oauth_access_token(row, settings)
            if refreshed:
                return refreshed
        if access:
            return access
    token = (service_token or "").strip()
    return token or None
