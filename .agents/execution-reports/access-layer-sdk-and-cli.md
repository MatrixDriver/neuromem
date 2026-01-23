# 执行报告：第一批（接入层）— Python SDK 与 CLI

## 元信息

| 项 | 值 |
|----|-----|
| 计划文件 | `.agents/plans/access-layer-sdk-and-cli.md` |
| 功能名称 | 接入层：NeuroMemory Python SDK + `neuromemory` CLI |
| 添加的文件 | `neuromemory/__init__.py`, `neuromemory/cli.py`, `tests/test_sdk.py`, `tests/test_cli.py` |
| 修改的文件 | `pyproject.toml`, `docs/API.md`, `docs/GETTING_STARTED.md` |
| 变更行数 | 约 +392 −20（含新增 4 个文件） |

---

## 验证结果

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 语法 / 代码检查 | ✓ | `python -m py_compile neuromemory/__init__.py neuromemory/cli.py` 通过；`read_lints` 无报错 |
| 类型检查 | — | 项目未配置 pyright/mypy，未执行 |
| 单元测试 | ✓ | `pytest tests/test_sdk.py tests/test_cli.py -v -m "not slow"`：5 通过，2 标记 slow 被排除；全量 7 通过 |
| 集成 / 入口 | ✓ | `uv pip install -e .`、`from neuromemory import NeuroMemory`、`neuromemory --help`、`neuromemory status`、`neuromemory graph export --user u` 均通过 |

---

## 进展顺利的部分

- **计划与实现一一对应**：`NeuroMemory` 的 `add` / `search` / `ask` / `get_graph`、`config`/`metadata` 行为、错误时 `ValueError` 均按计划实现。
- **CLI 与 Typer**：`neuromemory = "neuromemory.cli:app"` 可直接作为入口，无需 `main()` 包装；`status` / `add` / `search` / `ask` / `graph export` / `graph visualize` 全部实现。
- **`py-modules` 按计划补全**：`neuromemory` 入口报 `ModuleNotFoundError: private_brain` 后，按计划在 `[tool.setuptools]` 中增加 `py-modules`，问题解决。
- **测试与标记**：`test_ask_error_raises` 用 `patch.object(m._brain, "ask", ...)` 覆盖错误分支，无需 DB；`test_add_returns_memory_id`、`test_graph_export_exits_zero` 标 `@pytest.mark.slow`，与计划一致。
- **graph visualize**：`webbrowser.open` 包在 `try/except` 中，失败仍输出文件路径；vis-network 节点 `{id, label}`、边 `{from, to}` 按计划转换。

---

## 遇到的挑战

### 1. `neuromemory` 入口下 `private_brain` 找不到

- **现象**：`neuromemory --help` 时报 `ModuleNotFoundError: No module named 'private_brain'`。在项目根用 `python -c "from neuromemory import NeuroMemory"` 则正常。
- **原因**：通过 `[project.scripts]` 安装的 `neuromemory` 在运行时不 guarantee 项目根在 `sys.path`，而 `neuromemory` 依赖根目录的 `private_brain`、`health_checks` 等。
- **处理**：按计划在 `pyproject.toml` 的 `[tool.setuptools]` 中增加  
  `py-modules = ["config","private_brain","session_manager","coreference","consolidator","privacy_filter","health_checks"]`，重新 `uv pip install -e .` 后通过。

### 2. 验证命令在 PowerShell 下的写法

- **现象**：`cd /d d:\CODE\NeuroMemory && python -m py_compile ...` 在 PowerShell 中报错：`&&` 不是合法语句分隔符。
- **处理**：改为 `cd d:\CODE\NeuroMemory; python -m py_compile ...`，后续验证命令均用 `;`。

---

## 与计划的偏离

### 1. `graph export` 的 `--output` 参数类型

|  | 内容 |
|--|------|
| 计划 | `output: Optional[Path] = typer.Option(None,"--output","-o")`，`output.write_text(s, encoding="utf-8")` |
| 实际 | `output: Optional[str] = typer.Option(None, "--output", "-o")`，`Path(output).write_text(s, encoding="utf-8")` |
| 原因 | Typer 的 `Option` 在未显式 `path_type=Path` 时通常给出 `str`；采用 `str` 再 `Path(output)` 可减少配置，行为与计划一致。 |
| 类型 | 实现选择 |

### 2. `config` 非 None 时的 log 文案

|  | 内容 |
|--|------|
| 计划 | `"NeuroMemory(config=...) 暂未使用，使用 get_brain()"` |
| 实际 | `"NeuroMemory(config=...) 暂未使用 config，将使用默认 get_brain()"` |
| 原因 | 明确写出「config」和「默认 get_brain()」，便于排查和后续扩展。 |
| 类型 | 发现更好的方法 |

### 3. `docs/API.md` 的示例与结构

|  | 内容 |
|--|------|
| 计划 | 在原有代码块「下加一行」`from neuromemory import NeuroMemory` 并补充示例。 |
| 实际 | 在「Python SDK 接口」下新增单独代码块：`from neuromemory import NeuroMemory` 以及 `m.add` / `m.search` / `m.ask` / `m.get_graph` 示例；原 `class NeuroMemory` 定义保留为「接口定义（参考）」。 |
| 原因 | 把「可运行示例」和「接口定义」分开，避免拆散原有类定义，同时突出 `from neuromemory import NeuroMemory`。 |
| 类型 | 发现更好的方法 |

### 4. `docs/GETTING_STARTED.md` 新增「使用 CLI」小节

|  | 内容 |
|--|------|
| 计划 | 在「使用 SDK」中补充 CLI 示例：`neuromemory status`、`neuromemory add "..." --user u`。 |
| 实际 | 新增 `## 使用 CLI`，列出 `neuromemory status`、`add`、`search`、`ask`、`graph export`、`graph visualize` 等命令。 |
| 原因 | 与「使用 SDK」对称，便于快速查阅 CLI 用法。 |
| 类型 | 发现更好的方法 |

---

## 跳过的项目

| 项目 | 原因 |
|------|------|
| （无） | 计划中「要创建/修改的文件」均已实施；`docs/COMPONENTS.md` 未列入该清单，故未在本轮修改。 |

> **说明**：`docs/COMPONENTS.md` 中仍有「Python SDK (NeuroMemory 类) `[🚧 开发中]`」。若希望文档一致，可后续单独把该处改为 `[✅ 已实现]` 并微调说明。

---

## 建议

### 计划 / 文档

- **`COMPONENTS.md` 与 API/GETTING_STARTED 同步**：计划若涵盖「所有提到 NeuroMemory/CLI 的文档」，可把 `docs/COMPONENTS.md` 的「Python SDK (NeuroMemory 类)」明确写进「要修改的文件」，避免遗漏。
- **`graph export` 的 `output`**：若计划希望 API 直接暴露 `Path`，可在任务中写清「`typer.Option(..., path_type=Path)` 或等价方式」，减少实现时的类型选择歧义。

### 执行 / 验证

- **PowerShell 与 Bash 的差异**：`ENGINEERING_WORKFLOW.md` 或 `CLAUDE.md` 的「常用命令」若含 `&&`，可注明「Bash」或补充 PowerShell 版 `;`，便于在 Windows 上复现验证步骤。
- **类型检查**：若项目引入 pyright 或 mypy，建议在「验证命令」中增加 `pyright neuromemory/` 或 `mypy neuromemory/`，并在执行报告中保留「类型检查」一行。

### `CLAUDE.md` 可补充

- 安装与入口：`uv pip install -e .` 后可用 `from neuromemory import NeuroMemory` 和 `neuromemory` 命令。
- 常用 CLI：`neuromemory status`、`neuromemory add "..." --user <user>`、`neuromemory graph export --user <user>` 等。
- 若 `neuromemory` 报 `ModuleNotFoundError: private_brain`，需确认 `pyproject.toml` 的 `[tool.setuptools]` 已配置 `py-modules` 并重新 `uv pip install -e .`。
