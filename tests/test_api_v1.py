"""
/api/v1 与 health_checks 测试

- health_checks: check_neo4j, check_qdrant, check_llm_config
- /api/v1/memory, /api/v1/memory/search, /api/v1/graph, /api/v1/health
- /api/v1/ask 标 @pytest.mark.slow（需 LLM）
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
# /api/v1 端点集成测试（TestClient）
# =============================================================================


@pytest.fixture
def client():
    return TestClient(app)


class TestApiV1Health:
    """GET /api/v1/health：不依赖 DB 可测"""

    def test_health_returns_status_and_components(self, client):
        r = client.get("/api/v1/health")
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


class TestApiV1MemorySearch:
    """GET /api/v1/memory/search：无 DB 时返回空 memories 亦可"""

    def test_memory_search_returns_200_and_structure(self, client):
        r = client.get("/api/v1/memory/search", params={"query": "test", "user_id": "u", "limit": 2})
        assert r.status_code == 200
        data = r.json()
        assert "memories" in data
        assert "metadata" in data
        assert isinstance(data["memories"], list)
        assert len(data["memories"]) <= 2


class TestApiV1Graph:
    """GET /api/v1/graph：返回含 nodes、edges"""

    def test_graph_returns_nodes_and_edges(self, client):
        r = client.get("/api/v1/graph", params={"user_id": "u", "depth": 2})
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)


class TestApiV1MemoryPost:
    """POST /api/v1/memory：可能 200（DB 可用）或 500（DB 不可用）"""

    def test_memory_post_structure_or_error(self, client):
        r = client.post("/api/v1/memory", json={"content": "test memory", "user_id": "u"})
        # 200: 返回 memory_id；500: DB/ mem0 异常
        assert r.status_code in (200, 500)
        if r.status_code == 200:
            data = r.json()
            assert "memory_id" in data
            assert isinstance(data["memory_id"], str)


@pytest.mark.slow
class TestApiV1Ask:
    """POST /api/v1/ask：需 LLM，标 slow"""

    def test_ask_returns_answer_and_sources_or_error(self, client):
        r = client.post("/api/v1/ask", json={"question": "测试问题", "user_id": "u"})
        assert r.status_code in (200, 500)
        if r.status_code == 200:
            data = r.json()
            assert "answer" in data
            assert "sources" in data
            assert isinstance(data["sources"], list)
