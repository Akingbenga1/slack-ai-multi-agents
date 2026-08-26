"""System-wide tool discovery API tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.discovery.base import DiscoveredTool, DiscoveryNotConfiguredError
from api.app.discovery.deps import get_discovery_client
from api.app.discovery.http_client import HttpToolDiscoveryClient
from api.app.discovery.cli_client import CliDiscoveryClient
from api.app.discovery.tldr_store import init_schema
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


def _write_mini_tldr_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        init_schema(conn)
        rows = [
            (
                "zip",
                "common",
                "en",
                "zip",
                "Package and compress (archive) files into a Zip archive.",
                (
                    "# zip\n"
                    "> Package and compress (archive) files into a Zip archive.\n\n"
                    "- Add files/directories to a specific archive:\n\n"
                    "`zip {{[-r|--recurse-paths]}} {{path/to/compressed.zip}} {{path/to/file}}`\n\n"
                    "- Remove files/directories from a specific archive:\n\n"
                    "`zip {{[-d|--delete]}} {{path/to/compressed.zip}} {{path/to/file}}`\n"
                ),
            ),
            (
                "gzip",
                "common",
                "en",
                "gzip",
                "Compress/uncompress files with gzip compression (LZ77).",
                (
                    "# gzip\n"
                    "> Compress/uncompress files with gzip compression (LZ77).\n\n"
                    "- Compress a file:\n\n"
                    "`gzip {{path/to/file}}`\n\n"
                    "- Decompress a file:\n\n"
                    "`gzip {{[-d|--decompress]}} {{path/to/file.gz}}`\n"
                ),
            ),
            (
                "curl",
                "common",
                "en",
                "curl",
                "Transfers data from or to a server.",
                "# curl\n> Transfers data from or to a server.\n",
            ),
            (
                "in2csv",
                "common",
                "en",
                "in2csv",
                "Convert various tabular data formats to CSV.",
                (
                    "# in2csv\n"
                    "> Convert various tabular data formats to CSV.\n\n"
                    "- Convert a specific sheet from an XLSX file to CSV:\n\n"
                    "`in2csv --sheet={{sheet_name}} {{data.xlsx}}`\n"
                ),
            ),
        ]
        conn.executemany(
            """
            INSERT INTO pages (command, platform, language, title, description, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.execute(
            """
            INSERT INTO pages_fts(rowid, command, title, description, body)
            SELECT id, command, title, description, body FROM pages
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def tldr_db(tmp_path: Path) -> Path:
    db = tmp_path / "tldr_pages.db"
    _write_mini_tldr_db(db)
    return db


@pytest.fixture
def settings(tldr_db: Path) -> Settings:
    return Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_cli_db_path=str(tldr_db),
        discovery_mcp_service_url="https://discover.example/mcp",
        discovery_http_service_url="",
        discovery_timeout_seconds=5.0,
        discovery_cli_search_limit=10,
    )


def _owner_token(settings: Settings) -> str:
    return create_access_token(
        settings=settings,
        sub=str(DEMO_OWNER_ID),
        email="owner@example.com",
        role="platform_owner",
        tenant_id=None,
    )


def _admin_token(settings: Settings) -> str:
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )


def _auth(settings: Settings, *, role: str = "owner") -> dict[str, str]:
    token = _owner_token(settings) if role == "owner" else _admin_token(settings)
    return {"Authorization": f"Bearer {token}"}


class _StubClient:
    def __init__(self, tools: list[DiscoveredTool] | None = None, error: Exception | None = None):
        self.tools = tools or []
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def search(self, kind: str, query: str) -> list[DiscoveredTool]:
        self.calls.append((kind, query))
        if self.error is not None:
            raise self.error
        return list(self.tools)


def test_discovery_status_requires_auth(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            assert client.get("/discovery").status_code == 401
            res = client.get("/discovery", headers=_auth(settings, role="admin"))
            assert res.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_discovery_status_reports_configured_kinds(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            res = client.get("/discovery", headers=_auth(settings))
            assert res.status_code == 200
            body = res.json()
            assert body["kinds"]["cli"]["configured"] is True
            assert body["kinds"]["cli"]["env_key"] == "DISCOVERY_CLI_DB_PATH"
            assert body["kinds"]["mcp"]["configured"] is True
            assert body["kinds"]["http"]["configured"] is False
    finally:
        app.dependency_overrides.clear()


def test_cli_and_mcp_routes_share_stub_client(settings: Settings):
    stub = _StubClient(
        tools=[
            DiscoveredTool(
                id="csv-1",
                name="csv-export",
                summary="Export CSV",
                source="tldr",
                kind="cli",
            )
        ]
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_discovery_client] = lambda: stub
    try:
        with TestClient(app) as client:
            get_res = client.get(
                "/discovery/cli-tools",
                params={"query": "csv"},
                headers=_auth(settings),
            )
            assert get_res.status_code == 200
            assert get_res.json()["tools"][0]["name"] == "csv-export"

            post_res = client.post(
                "/discovery/mcp-tools",
                json={"query": "knowledge"},
                headers=_auth(settings),
            )
            assert post_res.status_code == 200
            assert post_res.json()["kind"] == "mcp"
            assert stub.calls == [("cli", "csv"), ("mcp", "knowledge")]
    finally:
        app.dependency_overrides.clear()


def test_cli_tools_searches_tldr_sqlite(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            res = client.get(
                "/discovery/cli-tools",
                params={"query": "compress files"},
                headers=_auth(settings),
            )
            assert res.status_code == 200
            body = res.json()
            assert body["kind"] == "cli"
            tools = {t["name"]: t for t in body["tools"]}
            assert "zip" in tools
            assert "gzip" in tools
            zip_tool = tools["zip"]
            assert zip_tool["source"] == "tldr"
            assert zip_tool["config"]["command"] == "zip"
            assert zip_tool["config"]["args"] == []
            assert "subcommands" in zip_tool["config"]
            first = next(iter(zip_tool["config"]["subcommands"].values()))
            assert set(first.keys()) == {"purpose", "usage"}
            assert "zip" in first["usage"]
            assert zip_tool["metadata"]["platform"] == "common"
            assert isinstance(zip_tool["metadata"]["examples"], list)
            assert zip_tool["metadata"]["examples"][0]["purpose"]
            assert zip_tool["metadata"]["examples"][0]["usage"]
    finally:
        app.dependency_overrides.clear()


def test_cli_or_ranking_finds_xlsx_csv_tools(settings: Settings):
    """OR + ranking should surface in2csv for a natural xlsx/csv phrase."""
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            res = client.get(
                "/discovery/cli-tools",
                params={"query": "extract xlsx to csv"},
                headers=_auth(settings),
            )
            assert res.status_code == 200
            body = res.json()
            names = [t["name"] for t in body["tools"]]
            assert "in2csv" in names
            # Higher coverage / name+desc agreement should keep in2csv near the top.
            assert names.index("in2csv") <= 2
            in2 = next(t for t in body["tools"] if t["name"] == "in2csv")
            assert in2["config"]["command"] == "in2csv"
            assert in2["config"]["subcommands"]
    finally:
        app.dependency_overrides.clear()


def test_cli_route_normalizes_any_source_config(settings: Settings):
    """Route-level normalize keeps CLI output registry-shaped for any client."""
    stub = _StubClient(
        tools=[
            DiscoveredTool(
                id="x",
                name="csvkit",
                summary="CSV toolkit",
                source="other",
                kind="cli",
                metadata={
                    "examples": [
                        {
                            "description": "Convert Excel to CSV",
                            "command": "in2csv {{file.xlsx}}",
                        }
                    ]
                },
            )
        ]
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_discovery_client] = lambda: stub
    try:
        with TestClient(app) as client:
            res = client.get(
                "/discovery/cli-tools",
                params={"query": "csv"},
                headers=_auth(settings),
            )
            assert res.status_code == 200
            tool = res.json()["tools"][0]
            assert tool["config"]["command"] == "csvkit"
            assert tool["config"]["args"] == []
            sub = tool["config"]["subcommands"]
            assert len(sub) == 1
            entry = next(iter(sub.values()))
            assert entry["purpose"] == "Convert Excel to CSV"
            assert entry["usage"] == "in2csv {{file.xlsx}}"
    finally:
        app.dependency_overrides.clear()


def test_search_missing_cli_db_returns_503(tmp_path: Path):
    missing = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_cli_db_path=str(tmp_path / "missing.db"),
        discovery_mcp_service_url="https://discover.example/mcp",
        discovery_http_service_url="",
        discovery_timeout_seconds=5.0,
    )
    stub = _StubClient(error=DiscoveryNotConfiguredError("cli"))
    app.dependency_overrides[get_settings] = lambda: missing
    app.dependency_overrides[get_discovery_client] = lambda: stub
    try:
        with TestClient(app) as client:
            res = client.get(
                "/discovery/cli-tools",
                params={"query": "pdf"},
                headers=_auth(missing),
            )
            assert res.status_code == 503
            detail = res.json()["detail"]
            assert detail["code"] == "discovery_not_configured"
            assert detail["kind"] == "cli"
            assert detail["env_key"] == "DISCOVERY_CLI_DB_PATH"
            assert stub.calls == []
    finally:
        app.dependency_overrides.clear()


def test_mcp_tools_stops_when_env_url_missing(tldr_db: Path):
    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_cli_db_path=str(tldr_db),
        discovery_mcp_service_url="",
        discovery_http_service_url="",
    )
    stub = _StubClient()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_discovery_client] = lambda: stub
    try:
        with TestClient(app) as client:
            status_res = client.get("/discovery", headers=_auth(settings))
            assert status_res.status_code == 200
            assert status_res.json()["kinds"]["mcp"]["configured"] is False
            assert status_res.json()["kinds"]["mcp"]["env_key"] == "DISCOVERY_MCP_SERVICE_URL"

            res = client.post(
                "/discovery/mcp-tools",
                json={"query": "postgres"},
                headers=_auth(settings),
            )
            assert res.status_code == 503
            detail = res.json()["detail"]
            assert detail["code"] == "discovery_not_configured"
            assert detail["env_key"] == "DISCOVERY_MCP_SERVICE_URL"
            assert stub.calls == []
    finally:
        app.dependency_overrides.clear()


def test_http_client_normalizes_upstream_payload(settings: Settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = json.loads(request.content.decode())
        assert body["query"]["text"] == "git"
        payload = {
            "results": [
                {
                    "identifier": "git-status",
                    "displayName": "git-status",
                    "description": "Show working tree",
                    "url": "https://example.com/git-status",
                    "homepage": "https://git-scm.com",
                }
            ]
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    # HTTP client still used for kind=http; give it a URL via settings copy
    http_settings = Settings(
        jwt_secret=settings.jwt_secret,
        discovery_cli_db_path=settings.discovery_cli_db_path,
        discovery_mcp_service_url=settings.discovery_mcp_service_url,
        discovery_http_service_url="https://discover.example/http",
        discovery_timeout_seconds=5.0,
    )
    client = HttpToolDiscoveryClient(http_settings, transport=transport)
    tools = client.search("http", "git")
    assert len(tools) == 1
    assert tools[0].name == "git-status"
    assert tools[0].summary == "Show working tree"
    assert tools[0].source == "https://example.com/git-status"
    assert tools[0].metadata.get("homepage") == "https://git-scm.com"


def test_cli_client_raises_when_db_missing(tmp_path: Path):
    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_cli_db_path=str(tmp_path / "nope.db"),
    )
    client = CliDiscoveryClient(settings)
    with pytest.raises(DiscoveryNotConfiguredError) as exc:
        client.search("cli", "calendar")
    assert exc.value.kind == "cli"


def test_cli_client_maps_hits(settings: Settings):
    client = CliDiscoveryClient(settings)
    tools = client.search("cli", "compress files")
    assert {t.name for t in tools} >= {"zip", "gzip"}
    assert all(t.kind == "cli" and t.source == "tldr" for t in tools)
    zip_tool = next(t for t in tools if t.name == "zip")
    assert zip_tool.config is not None
    assert zip_tool.config["command"] == "zip"
    assert zip_tool.config["subcommands"]
    sample = next(iter(zip_tool.config["subcommands"].values()))
    assert "purpose" in sample and "usage" in sample


def test_mcp_registry_normalizes_official_payload():
    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_mcp_service_url="https://registry.example",
        discovery_mcp_cache_ttl_seconds=0,
        discovery_timeout_seconds=5.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/v0.1/servers")
        assert request.url.params.get("search") == "postgres"
        assert request.url.params.get("version") == "latest"
        payload = {
            "servers": [
                {
                    "server": {
                        "name": "ai.waystation/postgres",
                        "description": "Connect to your PostgreSQL database.",
                        "version": "0.3.1",
                        "repository": {
                            "url": "https://github.com/waystation-ai/mcp",
                            "source": "github",
                        },
                        "remotes": [
                            {
                                "type": "streamable-http",
                                "url": "https://waystation.ai/postgres/mcp",
                            }
                        ],
                    },
                    "_meta": {
                        "io.modelcontextprotocol.registry/official": {
                            "status": "active",
                            "publishedAt": "2025-09-09T14:46:09.489652Z",
                            "isLatest": True,
                        }
                    },
                }
            ],
            "metadata": {"count": 1},
        }
        return httpx.Response(200, json=payload)

    from api.app.discovery.mcp_registry import OfficialMcpRegistryClient, _TtlCache

    client = OfficialMcpRegistryClient(
        settings, transport=httpx.MockTransport(handler), cache=_TtlCache()
    )
    tools = client.search("mcp", "postgres")
    assert len(tools) == 1
    assert tools[0].id == "ai.waystation/postgres"
    assert tools[0].name == "postgres"
    assert tools[0].summary.startswith("Connect to your PostgreSQL")
    assert tools[0].kind == "mcp"
    assert tools[0].metadata["transport"] == "streamable-http"
    assert tools[0].metadata["official"] is True
    assert tools[0].metadata["version"] == "0.3.1"


def test_mcp_registry_empty_url_disables():
    from api.app.discovery.mcp_registry import OfficialMcpRegistryClient

    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_mcp_service_url="",
    )
    client = OfficialMcpRegistryClient(settings)
    with pytest.raises(DiscoveryNotConfiguredError) as exc:
        client.search("mcp", "slack")
    assert exc.value.kind == "mcp"


def test_mcp_default_url_marks_configured(tmp_path: Path):
    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_cli_db_path=str(tmp_path / "missing.db"),
        discovery_mcp_service_url="https://registry.modelcontextprotocol.io",
        discovery_http_service_url="",
    )
    from api.app.discovery.base import kind_configured

    assert kind_configured(settings, "mcp") is True
    assert kind_configured(settings, "cli") is False


def test_mcp_missing_env_url_not_configured(tldr_db: Path):
    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_cli_db_path=str(tldr_db),
        discovery_mcp_service_url="",
        discovery_http_service_url="",
    )
    from api.app.discovery.base import kind_configured

    assert kind_configured(settings, "mcp") is False
    assert kind_configured(settings, "cli") is True


def test_http_client_timeout_maps_to_upstream_error():
    settings = Settings(
        jwt_secret="test-secret-at-least-32-chars-long!",
        discovery_http_service_url="https://discover.example/http",
        discovery_timeout_seconds=5.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    transport = httpx.MockTransport(handler)
    client = HttpToolDiscoveryClient(settings, transport=transport)
    with pytest.raises(Exception) as exc:
        client.search("http", "pdf")
    assert exc.value.__class__.__name__ == "DiscoveryUpstreamError"
    assert getattr(exc.value, "code") == "discovery_upstream_timeout"
    assert getattr(exc.value, "status_code") == 504


def test_discovery_does_not_require_tenant_header(settings: Settings):
    stub = _StubClient(tools=[])
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_discovery_client] = lambda: stub
    try:
        with TestClient(app) as client:
            res = client.post(
                "/discovery/cli-tools",
                json={"query": "xlsx"},
                headers=_auth(settings),
            )
            assert res.status_code == 200
            body = res.json()
            assert body["query"] == "xlsx"
            assert body["tools"] == []
            assert "tenant_id" not in body
    finally:
        app.dependency_overrides.clear()
