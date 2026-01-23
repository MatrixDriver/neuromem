"""
NeuroMemory SDK 测试

- get_graph 结构（status, nodes, edges）
- add 返回 memory_id（可标 @pytest.mark.slow / requires_db）
- search 返回 dict（memories, metadata）
- ask 在 brain 返回 error 时抛出 ValueError
"""

import pytest

from neuromemory import NeuroMemory


class TestNeuroMemory:
    """NeuroMemory 封装与错误行为"""

    def test_get_graph_structure(self) -> None:
        """get_graph 返回含 status、nodes、edges 的 dict。"""
        m = NeuroMemory()
        g = m.get_graph("u")
        assert "status" in g
        assert "nodes" in g
        assert "edges" in g

    @pytest.mark.slow
    def test_add_returns_memory_id(self) -> None:
        """add 成功时返回非空 memory_id。"""
        m = NeuroMemory()
        mid = m.add("sdk test", user_id="sdk_user")
        assert isinstance(mid, str)
        assert len(mid) > 0

    def test_search_returns_dict(self) -> None:
        """search 返回含 memories、metadata 的 dict。"""
        m = NeuroMemory()
        r = m.search("x", user_id="u", limit=2)
        assert "memories" in r
        assert "metadata" in r

    def test_ask_error_raises(self) -> None:
        """brain.ask 返回 error 时 SDK 抛出 ValueError。"""
        m = NeuroMemory()
        # 通过 mock 注入 error 响应；无 mock 时用真实 brain，若 ask 正常则跳过断言
        # 此处使用 patch 模拟 brain.ask 返回 {"answer":"","sources":[],"error":"模拟错误"}
        from unittest.mock import patch

        with patch.object(m._brain, "ask", return_value={"answer": "", "sources": [], "error": "模拟错误"}):
            with pytest.raises(ValueError, match="模拟错误"):
                m.ask("q", user_id="u")
