# Contributing / 参与贡献

[简体中文](#chinese) · [English](#english)

<a id="chinese"></a>
## 简体中文

感谢你帮助企业 AI 团队建立更清晰的业务模型。欢迎贡献行业定义、可复现的问题、类型与规则校验、文档翻译和可视化改进。

### 开始之前

- 在 [Issues](https://github.com/fdeopen/enterprise-ai-ontology/issues) 中查找已有讨论。较大的 DSL 变更请先描述业务需求、示例和兼容性影响。
- Bug 报告应包含 Python / 项目版本、执行命令、最小定义、预期结果与实际结果。
- 贡献行业模型时说明关键实体、关系、动作与 AI 场景，避免提交只有空目录或字段名的模板。
- 只使用虚构或获授权的数据；公开示例不得包含真实客户、人员资料或凭证。

### 本地开发

Fork 后克隆你的仓库，创建分支，再运行：

```bash
uv sync --locked --group dev
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run python -m build
```

需要 Python 3.11+。运行 `uv run enterprise-ontology serve` 验证工作台。测试使用本地数据与本地 HTTP 服务，不要求模型服务或 API Key。

### 改动要求

| 改动类型 | 验证与维护要求 |
| --- | --- |
| 行业模型 | YAML / JSON 语义一致，附正反记录；通过结构与引用校验 |
| DSL / 规则 | 覆盖实际行为变化及失败路径，说明兼容性影响 |
| JSON Schema | 修改模型后运行 `uv run enterprise-ontology schema > schema/ontology.schema.json` |
| 前端 | 验证对象详情、编辑失败后的状态、导入导出及布局；说明未验证的平台 |
| 文档 | 验证文件链接与可复制命令，保持中英文 README 的功能说明一致 |

文档和低风险展示修改不需要为实现细节新增测试。不要添加会执行 DSL 内任意代码的功能。文件、网络或流程执行应由外部业务系统负责，并保留明确边界。

### 提交 Pull Request

围绕一个清晰的问题组织改动。描述修改原因、行为变化、验证方式和已知限制；文档变更附上读者可以执行的示例，UI 变更附上有帮助的截图。不要提交虚拟环境、生成报告、构建产物或真实业务数据。提交贡献表示你同意按本项目的 [MIT License](LICENSE) 分发该贡献。

请以具体证据讨论实现，对参与者保持尊重。作者与社区信息见 [README](README.md#community)。

<a id="english"></a>
## English

Thank you for helping enterprise AI teams build clearer business models. Contributions are welcome for industry definitions, reproducible issues, type and rule validation, translations, and visualization.

### Before you start

- Check [existing issues](https://github.com/fdeopen/enterprise-ai-ontology/issues). Discuss substantial DSL changes with a business case, example, and compatibility implications first.
- Bug reports should include Python and package versions, the command used, a minimal definition, expected behavior, and actual behavior.
- Industry contributions should explain the core entities, relationships, actions, and AI scenarios, rather than only providing empty folders or field names.
- Use fictional or authorized data. Public examples must not contain real customer or personnel information or credentials.

### Local development

Fork and clone the repository, create a branch, then run:

```bash
uv sync --locked --group dev
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run python -m build
```

Python 3.11+ is required. Start the workbench with `uv run enterprise-ontology serve`. Tests use local data and local HTTP servers; no model service or API key is needed.

### Change expectations

| Change | Validation and maintenance |
| --- | --- |
| Industry model | Keep YAML and JSON equivalent, include positive and negative records, and validate structure and references |
| DSL / rules | Test behavioral changes and failure paths; explain compatibility impact |
| JSON Schema | After changing models, run `uv run enterprise-ontology schema > schema/ontology.schema.json` |
| Frontend | Check object details, failed edits, imports, exports, and layout; identify unverified platforms |
| Documentation | Verify relative links and executable examples; keep both READMEs consistent |

Documentation and low-risk presentation changes do not require new tests mirroring implementation details. Do not add arbitrary code execution to the DSL. File operations, external calls, and workflow execution belong in the integrating business application with explicit boundaries.

### Pull requests

Keep each PR focused on one clear problem. Explain the motivation, behavior changes, validation, and known limitations. Include runnable examples for documentation and useful screenshots for UI changes. Exclude virtual environments, generated reports, build artifacts, and real business data. Contributions are distributed under this project's [MIT License](LICENSE).

Discuss implementations with concrete evidence and treat participants respectfully. Author and community information is in the [README](README.en.md#community).
