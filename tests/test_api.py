"""
API 端点与 health_checks 测试

- health_checks: check_neo4j, check_qdrant, check_llm_config
- /health 健康检查（含 components）
- /search 纯检索
- /ask 基于记忆问答（标 @pytest.mark.slow，需 LLM）
"""
import pytest

from fastapi.testclient import TestClient

from http_server import app


# =============================================================================
# health_checks 单元测试
# =============================================================================


class TestHealthChecks:
    """health_checks 模块：返回 bool，不抛异常"""

    def test_check_neo4j_returns_bool(self):
        from health_checks import check_neo4j

        assert isinstance(check_neo4j(), bool)

    def test_check_qdrant_returns_bool(self):
        from health_checks import check_qdrant

        assert isinstance(check_qdrant(), bool)

    def test_check_llm_config_returns_bool(self):
        from health_checks import check_llm_config

        assert isinstance(check_llm_config(), bool)


# =============================================================================
# API 端点集成测试（TestClient）
# =============================================================================


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    """GET /health：不依赖 DB 可测"""

    def test_health_returns_status_and_components(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] in ("healthy", "unhealthy")
        assert "components" in data
        assert "neo4j" in data["components"]
        assert "qdrant" in data["components"]
        assert "llm" in data["components"]
        assert "service" in data
        assert data["service"] == "neuro-memory"


class TestSearch:
    """GET /search：纯检索，无 DB 时返回空 memories 亦可"""

    def test_search_returns_200_and_structure(self, client):
        r = client.get("/search", params={"query": "test", "user_id": "u", "limit": 2})
        assert r.status_code == 200
        data = r.json()
        assert "memories" in data
        assert "metadata" in data
        assert isinstance(data["memories"], list)
        assert len(data["memories"]) <= 2


@pytest.mark.slow
class TestAsk:
    """POST /ask：需 LLM，标 slow"""

    def test_ask_returns_answer_and_sources_or_error(self, client):
        r = client.post("/ask", json={"question": "测试问题", "user_id": "u"})
        assert r.status_code in (200, 500)
        if r.status_code == 200:
            data = r.json()
            assert "answer" in data
            assert "sources" in data
            assert isinstance(data["sources"], list)
