"""
NeuroMemory CLI 测试

- status: 不依赖 DB，exit 0，输出含 neo4j/qdrant
- help: 含 add、search、graph、status
- graph export: exit 0，输出含 status 或 nodes（可标 slow）
"""

import pytest
from typer.testing import CliRunner

from neuromemory.cli import app

runner = CliRunner()


def test_status_exits_zero() -> None:
    """neuromemory status 退出码 0，输出含 neo4j 或 qdrant。"""
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 0
    assert "neo4j" in r.output or "qdrant" in r.output


def test_help() -> None:
    """--help 列出 add、search、graph、status。"""
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "add" in r.output
    assert "search" in r.output
    assert "graph" in r.output
    assert "status" in r.output


@pytest.mark.slow
def test_graph_export_exits_zero() -> None:
    """neuromemory graph export --user u 退出码 0，输出含 status 或 nodes。"""
    r = runner.invoke(app, ["graph", "export", "--user", "u"])
    assert r.exit_code == 0
    assert "status" in r.output or "nodes" in r.output
