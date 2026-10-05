# Security / 安全说明

[简体中文](#chinese) · [English](#english)

<a id="chinese"></a>
## 简体中文

这是本地建模工作台，无身份认证或多人隔离，仅允许监听回环地址。不要将它直接暴露为公网服务。

JSON/YAML 定义不会执行 Python、Shell 或模板代码。解析器拒绝重复键、YAML alias / merge、自定义对象构造及非 JSON 值，并限制大小与嵌套深度。CLI 只写入明确指定的输出路径，并拒绝覆盖已有输出；Web 不暴露用户文件系统。

离线 HTML 包含完整模型定义。分享前请确认字段名、业务描述和规则适合接收方；`sensitive` 只是元数据标记，不自动脱敏或实施权限控制。工具不要求输入真实人员资料。

### 报告问题

不要将漏洞利用细节、真实业务数据或可用凭证提交到公开 Issue。优先使用仓库 **Security → Report a vulnerability** 入口（如果维护者已启用）；否则通过 [FDEChina.ai](https://fdechina.ai/) 或微信公众号 **FDE前线** 联系作者 **越哥聊AI**，先约定私密沟通渠道，再提交敏感复现信息。

请提供受影响版本、最小复现、影响范围及可选修复建议。项目尚未承诺安全响应 SLA 或旧版本维护周期，当前维护以默认分支为准。

<a id="english"></a>
## English

This is a local modeling workbench without authentication or multi-user isolation. It only accepts loopback bindings and should not be exposed directly as an internet service.

JSON/YAML definitions do not execute Python, shell commands, or template code. The parser rejects duplicate keys, YAML aliases and merges, dynamic object construction, and non-JSON values, with size and nesting limits. The CLI writes only to explicit output paths and refuses to overwrite existing output. The web API does not expose user filesystem paths.

Offline HTML contains the full model. Review field names, business descriptions, and rules before sharing. The `sensitive` flag is metadata, not redaction or access control. The toolkit does not require real personnel data.

### Reporting a vulnerability

Do not publish exploit details, real business data, or credentials in a public issue. Prefer the repository's **Security → Report a vulnerability** entry if maintainers have enabled it. Otherwise, contact **越哥聊AI** through [FDEChina.ai](https://fdechina.ai/) or the **FDE前线** WeChat Official Account to establish a private channel before sending sensitive reproduction details.

Include the affected version, a minimal reproduction, impact, and an optional proposed fix. The project does not currently commit to a security response SLA or maintenance windows for older versions; maintenance focuses on the default branch.
