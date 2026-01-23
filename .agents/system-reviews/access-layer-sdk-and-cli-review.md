# 系统审查：第一批（接入层）— Python SDK 与 CLI

## 元信息

- **审查的计划**：`.agents/plans/access-layer-sdk-and-cli.md`
- **执行报告**：`.agents/execution-reports/access-layer-sdk-and-cli.md`
- **日期**：2025-01-23

**参考的流程文档**：`docs/ENGINEERING_WORKFLOW.md` 中 `core_piv_loop/plan-feature`、`core_piv_loop/execute` 的职责与检查要点（项目内未找到独立的 `plan-feature.md` / `execute.md` 文件）。

---

## 整体对齐分数：8/10

**评分依据**：
- 计划中的 8 个逐步任务、验收标准、验证命令均被实现或执行；`py-modules` 的「若报错则添加」被正确触发并执行。
- 执行报告中的 4 项偏离均属**合理偏离**（实现选择、发现更好的方法），无违反明确约束或引入技术债的坏偏离。
- 扣除 2 分：① **问题陈述与「要修改的文件」不一致**：问题陈述提到「文档（API.md、**COMPONENTS**、GETTING_STARTED）」，要创建/修改仅列 API.md、GETTING_STARTED，COMPONENTS 未列入，导致 COMPONENTS 中 NeuroMemory 仍为 🚧；② **验证命令的 Shell 假设**：计划中的 `&&` 在 Windows PowerShell 下不可用，执行时需临时改为 `;`，计划与执行指导均未事先约定 shell 或提供多 shell 示例。

---

## 偏离分析

以下均来自执行报告「与计划的偏离」。

---

### 1. `graph export` 的 `--output` 参数类型

| 项目 | 内容 |
|------|------|
| **divergence** | `output` 由 `Optional[Path]` 改为 `Optional[str]`，写文件时用 `Path(output).write_text(...)` |
| **planned** | `output: Optional[Path] = typer.Option(None,"--output","-o")`，`output.write_text(s, encoding="utf-8")` |
| **actual** | `output: Optional[str] = typer.Option(None, "--output", "-o")`，`Path(output).write_text(s, encoding="utf-8")` |
| **reason** | Typer 的 `Option` 未指定 `path_type=Path` 时通常返回 `str`；用 `str` 再 `Path()` 减少配置，行为等价 |
| **classification** | ✅ good |
| **justified** | yes |
| **root_cause** | 计划假定「写 `Path` 即得 `Path`」，未写明 Typer 需 `path_type=Path` 或约定「`str`+`Path()` 为可接受实现」；属**计划对框架默认行为的假设未显式化**，执行者做了合理等效实现。 |

---

### 2. `config` 非 None 时的 log 文案

| 项目 | 内容 |
|------|------|
| **divergence** | debug 文案由「暂未使用，使用 get_brain()」改为「暂未使用 config，将使用默认 get_brain()」 |
| **planned** | `"NeuroMemory(config=...) 暂未使用，使用 get_brain()"` |
| **actual** | `"NeuroMemory(config=...) 暂未使用 config，将使用默认 get_brain()"` |
| **reason** | 明确写出「config」与「默认 get_brain()」，便于排查与后续扩展 |
| **classification** | ✅ good |
| **justified** | yes |
| **root_cause** | 无；属**实施中发现的更优表述**，计划无需改。 |

---

### 3. `docs/API.md` 的示例与结构

| 项目 | 内容 |
|------|------|
| **divergence** | 未在既有 class 代码块「下加一行」，而是新增独立「可运行示例」代码块，原 class 保留为「接口定义（参考）」 |
| **planned** | 在原有代码块「下加一行」`from neuromemory import NeuroMemory` 并补充示例 |
| **actual** | 新增单独代码块：`from neuromemory import NeuroMemory` 与 `m.add`/`m.search`/`m.ask`/`m.get_graph` 示例；原 `class NeuroMemory` 仍保留为「接口定义（参考）」 |
| **reason** | 将可运行示例与接口定义分离，不拆散原 class 定义，同时突出 `from neuromemory import NeuroMemory` |
| **classification** | ✅ good |
| **justified** | yes |
| **root_cause** | 无；属**发现更好的文档结构**。计划中的「下加一行」若会导致段落臃肿或拆散既有结构，执行者采用更清晰分块是合理取舍。 |

---

### 4. `docs/GETTING_STARTED.md` 新增「使用 CLI」小节

| 项目 | 内容 |
|------|------|
| **divergence** | 计划为在「使用 SDK」中补充 CLI 示例；实际新增独立 `## 使用 CLI` 及多条命令 |
| **planned** | 在「使用 SDK」中补充 CLI 示例：`neuromemory status`、`neuromemory add "..." --user u` |
| **actual** | 新增 `## 使用 CLI`，列出 `neuromemory status`、`add`、`search`、`ask`、`graph export`、`graph visualize` 等 |
| **reason** | 与「使用 SDK」对称，便于单独查阅 CLI |
| **classification** | ✅ good |
| **justified** | yes |
| **root_cause** | 无；属**在满足计划要求之上的增强**，未违背任何约束。 |

---

## 模式遵循

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 遵循了代码库架构 | ✓ | `neuromemory` 包、`[project.scripts]`、`py-modules`、`tests/` 与既有 layout 一致；CLI 通过 `NeuroMemory()` 委托 `get_brain()`，与「不重复业务逻辑」一致 |
| 使用了已记录的模式 | ✓ | 错误时 `ValueError` 与 http_server 的「失败即报错」一致；`logger = logging.getLogger("neuromemory.sdk")` 按计划；`@pytest.mark.slow`、`CliRunner` 与 `test_api_v1` 等既有用法一致 |
| 正确应用了测试模式 | ✓ | `TestNeuroMemory`、`test_ask_error_raises` 用 `patch.object` 覆盖错误分支；`test_add_returns_memory_id`、`test_graph_export_exits_zero` 标 `@pytest.mark.slow`；`test_status_exits_zero`、`test_help` 不依赖 DB |
| 满足了验证要求 | ✓ | `py_compile`、`uv pip install -e .`、`from neuromemory import NeuroMemory`、`neuromemory --help`、`neuromemory status`、`pytest ... -m "not slow"` 均执行且通过 |

---

## 系统改进行动

以下为基于本审查的**可操作**建议，按「更新 CLAUDE.md」「更新计划/plan-feature 指导」「更新 execute 指导」「新命令」归类。

---

### 更新 CLAUDE.md

- [ ] **补充接入层与 CLI 的使用与排错**（建议放在「常用命令」或新小节「Python SDK / CLI」）：
  - `uv pip install -e .` 后可用 `from neuromemory import NeuroMemory` 和 `neuromemory` 命令；
  - 常用：`neuromemory status`、`neuromemory add "..." --user <user>`、`neuromemory graph export --user <user>` 等；
  - 若 `neuromemory` 报 `ModuleNotFoundError: No module named 'private_brain'`：检查 `pyproject.toml` 的 `[tool.setuptools]` 是否包含 `py-modules = ["config","private_brain","session_manager","coreference","consolidator","privacy_filter","health_checks"]`，并重新执行 `uv pip install -e .`。

- [ ] **验证命令的 Shell 约定**（建议放在「常用命令」或「开发约定」）：
  - 若文档/计划中的验证命令使用 `&&` 串联，在 **Windows PowerShell** 下应改为 `;`，或注明「Bash」并另给 PowerShell 示例（如：`cd d:\CODE\NeuroMemory; python -m py_compile neuromemory/__init__.py neuromemory/cli.py`）。

---

### 更新 plan-feature / 计划模板

（依据 `docs/ENGINEERING_WORKFLOW.md` 中对 plan-feature 的摘要；若存在独立 plan-feature 命令或模板，可将下列内容加入其检查项或 GOTCHA。）

- [ ] **「要创建/修改的文件」与问题陈述一致**：若**问题陈述**中提到某文档 D（如 COMPONENTS.md、API.md）需体现本特性，则**要创建/修改的文件**必须包含 D；若不修改 D，须在计划中显式写出「不修改 D，原因：…」。

- [ ] **Typer/Click 的 `Path` 与 `path_type`**：当逐步任务要求 `typer.Option(..., path_type=Path)` 或 `Optional[Path]` 且对 `output` 做 `output.write_text(...)` 时，须在 IMPLEMENT 或 GOTCHA 中写明下列之一：  
  - 使用 `typer.Option(..., path_type=Path)` 得到 `Path`；或  
  - 约定采用 `Optional[str]` + `Path(output).write_text(...)` 为可接受等价实现。  
  以避免执行者在「框架默认返回 str」与「计划写 Path」之间自行猜测。

- [ ] **验证命令的 Shell 与平台**：若计划中的「验证命令」或「VALIDATE」使用 `&&`、`||` 等 Bash 语法，须注明「Bash」或「Linux/macOS」；若需支持 Windows，应补充 PowerShell 写法（如 `;` 代替 `&&`），或写「Windows 下将 `&&` 改为 `;`」。

---

### 更新 execute 指导 / 执行检查清单

（依据 `docs/ENGINEERING_WORKFLOW.md` 2.3 及 execute 的「按计划实施」「边做边验证」；若存在独立 execute 命令或检查清单，可加入下列项。）

- [ ] **执行验证命令前的 Shell 检查**：若计划中的验证命令含 `&&`（或仅给出 Bash 示例），且当前环境为 **Windows PowerShell**，则先将 `&&` 替换为 `;` 再执行，或按计划/CLAUDE 中的 PowerShell 示例执行；执行报告中可简要记录「在 PowerShell 下使用 `;`」。

- [ ] **`[project.scripts]` 与 `py-modules` 的安装后验证**：对引入 `[project.scripts]` 入口且依赖项目根模块（如 `private_brain`）的计划，在 `uv pip install -e .` 之后，除 `python -c "from neuromemory import NeuroMemory"` 外，应增加：  
  - `neuromemory --help` 或 `neuromemory status`  
  以验证通过 console_scripts 调用时 `py-modules` 已生效；若失败且报 `ModuleNotFoundError`，按计划中的「若…则添加 py-modules」处理并重装。  
  （本计划已在 VALIDATE 含 `neuromemory --help`、`neuromemory status`，建议泛化为「凡新增 [project.scripts] 且依赖根模块，执行清单须包含一次通过入口点的调用」。）

---

### 创建新命令

- **不推荐新增命令**。  
  - PowerShell 与 Bash 的差异：在 CLAUDE、plan、execute 中补充说明即可。  
  - `py-modules` 的按需添加：计划已有「若 ModuleNotFoundError 则加 py-modules」，执行依此处理即可。  
  - 未发现需要自动化且重复 3 次以上的独立流程。

---

## 关键学习

### 进展顺利的部分

- **计划自带的「若…则…」可执行**：`py-modules` 的「若 `from neuromemory import NeuroMemory` 报 `No module named 'private_brain'` 则添加 py-modules」被准确触发并执行，避免了计划与实现脱节。
- **GOTCHA 与框架行为**：计划对 `graph visualize` 的 vis-network 节点/边、`webbrowser` 的 `try/except` 有明确 GOTCHA，执行按此实现，减少了试错。
- **测试策略与标记**：`@pytest.mark.slow`、`requires_db` 的用法与既有 `test_api_v1`、`test_cognitive` 一致；`test_ask_error_raises` 用 mock 覆盖错误分支，不依赖 DB，符合「not slow」可全过。
- **执行报告与审查的衔接**：执行报告对 4 项偏离均给出「计划 / 实际 / 原因 / 类型」，便于 system-review 直接做 good/bad 分类与 root_cause，无需再翻代码。

### 需要改进的部分

- **问题陈述与修改范围一致**：问题陈述写出「API.md、COMPONENTS、GETTING_STARTED」需体现 NeuroMemory/CLI，但「要创建/修改的文件」仅含 API.md、GETTING_STARTED，COMPONENTS 被遗漏，导致 COMPONENTS 中 NeuroMemory 仍为 🚧。应在 plan-feature 或计划模板中增加：**问题陈述中出现的文档若与「要修改的文件」不一致，须在计划中显式排除并说明理由**。
- **验证命令的默认运行环境**：计划未声明「验证命令默认在 Bash 还是 PowerShell」；在 Windows 上执行时，`&&` 需临时改为 `;`。应在 plan 的「验证命令」或 execute 的「执行前检查」中约定：**给出 Bash 时，同时注明 PowerShell 的替换写法，或声明「Windows 下将 `&&` 改为 `;`」**。
- **Typer/Path 的预设**：计划写 `Optional[Path]` 与 `output.write_text`，未考虑 Typer 默认返回 `str`。类似「与运行环境/框架默认行为强相关」的类型，应在 IMPLEMENT 或 GOTCHA 中写清：**要么 `path_type=Path`，要么明确 `str`+`Path()` 为可接受方案**。

### 下次实施可尝试的改进

1. **写计划时**：对「问题陈述」里出现的每个文档做一次核对，确保其要么在「要创建/修改的文件」中，要么在计划中写「不修改，原因」。
2. **写计划时**：对 Typer/Click 的 `Path`、`File` 等类型，在任务中加一行 GOTCHA：「Typer 默认给 str；若需 `Path`，写 `path_type=Path` 或约定 `str`+`Path()`。」
3. **写验证命令时**：若使用 `&&`，在同一节末尾加一句：「PowerShell：以 `;` 代替 `&&`。」
4. **execute 完成后**：在「运行 `neuromemory --help` / `neuromemory status`」一步，若失败且为 `ModuleNotFoundError: private_brain`，先按计划的 py-modules 步骤修好再继续，避免误判为「环境问题」而跳过。
