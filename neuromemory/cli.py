"""
NeuroMemory CLI - Typer 入口

命令: add, search, ask, graph export, graph visualize, status
"""

import json
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional

import typer

from health_checks import check_llm_config, check_neo4j, check_qdrant
from private_brain import get_brain

app = typer.Typer()
graph_app = typer.Typer()
app.add_typer(graph_app, name="graph")


@app.command()
def status() -> None:
    """检查 Neo4j、Qdrant、LLM 配置状态。"""
    neo = check_neo4j()
    qd = check_qdrant()
    llm = check_llm_config()
    typer.echo("neo4j: ok" if neo else "neo4j: fail")
    typer.echo("qdrant: ok" if qd else "qdrant: fail")
    typer.echo("llm: ok" if llm else "llm: fail")


@app.command()
def add(
    content: str,
    user: str = typer.Option("default", "--user", "-u"),
) -> None:
    """添加记忆。"""
    brain = get_brain()
    result = brain.add(content, user_id=user)
    if result.get("status") == "error":
        typer.echo(f"错误: {result.get('error', '添加失败')}", err=True)
        sys.exit(1)
    typer.echo(result["memory_id"])


@app.command()
def search(
    query: str,
    user: str = typer.Option("default", "--user", "-u"),
    limit: int = typer.Option(10, "--limit", "-l"),
) -> None:
    """混合检索记忆。"""
    brain = get_brain()
    result = brain.search(query, user_id=user, limit=limit)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def ask(
    question: str,
    user: str = typer.Option("default", "--user", "-u"),
) -> None:
    """基于记忆回答问题。"""
    brain = get_brain()
    result = brain.ask(question, user_id=user)
    if result.get("error"):
        typer.echo(f"错误: {result['error']}", err=True)
        sys.exit(1)
    typer.echo(result["answer"])


@graph_app.command("export")
def graph_export(
    user: str = typer.Option("default", "--user", "-u"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """导出知识图谱为 JSON（默认 stdout）。"""
    brain = get_brain()
    graph = brain.get_user_graph(user_id=user)
    s = json.dumps(graph, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(s, encoding="utf-8")
    else:
        typer.echo(s)


@graph_app.command("visualize")
def graph_visualize(
    user: str = typer.Option("default", "--user", "-u"),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser"),
) -> None:
    """生成知识图谱 HTML 并用浏览器打开。"""
    brain = get_brain()
    g = brain.get_user_graph(user_id=user)
    nodes = [
        {"id": n["id"], "label": n.get("name", n["id"])}
        for n in g.get("nodes", [])
    ]
    edges = [
        {"from": e["source"], "to": e["target"]}
        for e in g.get("edges", [])
    ]
    nodes_js = json.dumps(nodes, ensure_ascii=False)
    edges_js = json.dumps(edges, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
</head><body><div id="n" style="width:100%;height:600px;"></div>
<script>
var n = {nodes_js}, e = {edges_js};
var c = document.getElementById("n");
new vis.Network(c, {{nodes: new vis.DataSet(n), edges: new vis.DataSet(e)}}, {{}});
</script></body></html>"""
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(html)
        tmp_path = tmp.name
    if open_browser:
        try:
            webbrowser.open("file://" + tmp_path)
        except Exception:
            pass
    typer.echo(f"已生成: {tmp_path}")
