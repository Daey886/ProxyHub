# GitHub Actions 自动化工作流

本页说明 ProxyHub 当前项目中已启用的自动化，以及哪些步骤会自动执行、哪些步骤必须人工确认。

> 自动化只负责检查、生成候选变更和报告；生产规则仍以人工审核并合并到 `main` 为准。任何工作流失败时，都不得把不完整或未验证的规则发布到生产分支。

## 一览

| 工作流 | 触发方式 | 自动执行内容 | 是否自动修改 `main` |
|---|---|---|---|
| `PR Quality Gate` | PR 创建、更新、重新打开 | 测试、规则新鲜度、安全审计、变更报告、Python/JS/YAML 校验 | 否 |
| `Cloudflare AI PR Review` | PR 创建、更新、重新打开；也可手动指定 PR | 使用 Cloudflare Workers AI 审查；自动维护 PR 可在通过后启用受保护自动合并 | 仅限受信任自动维护 PR |
| `Sync AI Leaderboards & Auto Update Rules` | 每小时整点、手动触发 | 抓取 AI 平台、生成各客户端规则、上传审计报告、创建或更新 PR | 否 |
| `Scheduled Rules Security Audit` | 每小时第 30 分钟、手动触发 | 审计正式规则；失败时创建告警 Issue | 否 |
| `Build domain candidate PR` | 域名申请 Issue 新建、编辑、重新打开 | 校验官方证据、生成候选规则、创建 Draft PR | 否 |
| `Triage Issues` | Issue 新建、重新打开 | 添加分类标签、请求补充复现信息 | 否 |
| `External Links and Rules Audit` | 每日 UTC 03:15、手动触发 | 检查文档中的外部链接和规则资源 | 否 |
| `Keep GitHub Pages Alive` | 每小时、手动触发 | 检查 Pages；失败时请求 Pages 重建 | 仅请求 Pages 重建 |
| `Release validation and publish` | 手动触发 | 校验版本、测试、审计、创建 Git tag 和 GitHub Release | 否；发布前需人工确认 |
| `pages-build-deployment` | GitHub Pages 平台自动触发 | 发布 `docs/` 网站 | 由 GitHub Pages 管理 |
| `Weekly AI Automation Knowledge Update` | 每 7 天（周日 03:40 UTC）；也可手动触发 | 使用 `@cf/cloudflare/clef-flash` 整理项目自动化知识库并创建候选 PR | 否 |

> Cloudflare AI 审查分为两类：人工 PR 只发表评论，不自动合并；`automation/*` 和 `dependabot/*` 的自动维护 PR 在静默 5 分钟后才审查，只有模型明确输出“结论：通过”时才启用 GitHub 受保护自动合并。它仍不能绕过分支保护、必需检查或仓库规则。模型不会修改文件。

启用前，在 GitHub 仓库 **Settings → Secrets and variables → Actions** 添加：

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`：只授予该账户 Workers AI 推理所需的最小权限，不要写入仓库文件或日志。

未配置这两个 Secret 时，工作流会安全跳过，不会失败。工作流不 checkout PR 代码，而是通过 GitHub API 读取 diff；PR 标题和 diff 均作为不可信文本传给模型。模型只发表评论，不获得仓库写入权限。

启用后，Cloudflare Workers AI 默认使用 `@cf/meta/llama-3.1-8b-instruct`。如需更换模型，修改工作流中的 `CF_MODEL`，并先验证账户已启用该模型。

### 每周自动化学习库更新

`Weekly AI Automation Knowledge Update` 每 7 天运行一次，使用 `@cf/cloudflare/clef-flash` 读取有界的工作流、知识库、测试约束和近期验证历史，生成增量候选内容，写入 `docs/ai-automation-knowledge.md` 并创建或更新 `automation/ai-knowledge-weekly` PR。

该流程不是模型微调，不会把凭据或不可信文本当作指令，也不会直接修改 `main`。候选内容必须经过 PR 质量门禁、Cloudflare AI 审查和仓库分支保护后才能合并；没有可靠新增内容时不应创建有效变更。

### Cloudflare AI 审查流程

1. PR 创建或更新后触发工作流。
2. 读取 PR diff，并限制请求大小。
3. 检查规则安全、Actions 权限、外部输入、凭据泄露、明显逻辑错误和测试缺口。
4. 调用 Cloudflare Workers AI API。
5. 将中文审查摘要作为 PR 评论发布。
6. 维护者结合本地测试、规则审计和人工证据审核决定是否合并。

Cloudflare API 失败、返回空结果或格式异常时，工作流失败并保留原 PR 不变；不会生成代码补丁，也不会自动合并。

## 自动运行流程

### 1. Pull Request 质量门禁

所有 PR 在创建、更新或重新打开时运行 `PR Quality Gate`，包括：

- `python -m unittest discover -s tests -v`
- 检查生成规则是否与生成器一致
- `scripts/rules_audit.py` 规则安全审计
- 生成并上传规则变更报告 artifact
- Python 编译检查
- `node --check clash/extension-script.js`
- 工作流和版本 YAML 解析检查
- `git diff --check` 空白字符检查

质量门禁失败时，PR 不应合并。

### 2. AI 规则每小时同步

`Sync AI Leaderboards & Auto Update Rules` 每小时抓取上游平台并运行 `scripts/auto_update_ai.py`。执行顺序为：

1. 安装校验依赖并运行测试。
2. 抓取并生成规则。
3. 抓取失败或校验失败时立即失败关闭，不写入不完整结果。
4. 生成 JSON 审计报告并作为 artifact 保存。
5. 有变更时更新 `automation/sync-ai-rules` 分支。
6. 创建或更新 PR，等待人工审核。

该流程不会直接推送或合并 `main`。

### 3. 域名申请与官方证据

用户应通过 Issue 模板提交域名申请，至少提供：域名、目标规则集、官方来源或证据、客户端、现象和必要日志。`Build domain candidate PR` 会：

1. 校验 Issue 是否包含域名申请字段。
2. 验证官方证据。
3. 校验域名格式和目标规则集。
4. 写入候选清单并生成所有客户端规则。
5. 运行测试。
6. 创建或更新 Draft PR。

Issue 内容是不可信输入，不会被当作 shell、脚本或配置执行；候选 PR 不会自动合并。

### 4. 定时规则安全审计

`Scheduled Rules Security Audit` 每小时审计 `main` 上的正式规则。发现 IP 地址、过宽根域名、格式错误、跨客户端不一致等问题时，工作流失败并创建或更新告警 Issue。告警不会自动修改规则。

### 5. 链接和 Pages 检查

- `External Links and Rules Audit` 每天检查 README、文档和规则中的外部链接。
- `Keep GitHub Pages Alive` 每小时检查 `https://daey886.github.io/ProxyHub/` 是否返回正常 HTML。
- Pages 检查失败后仅请求 GitHub Pages 重建，不宣称已经修复。

### 6. Issue 自动分流

`Triage Issues` 会根据标题和正文添加 `triage` 及规则、链接、客户端或功能分类标签，并回复复现信息清单。它不会自动关闭 Issue，也不会根据关键词修改生产规则。

## 发布流程

版本发布工作流 `Release validation and publish` 必须由维护者在 Actions 页面手动运行，并填写：

- `version`：不带 `v` 的三段式版本号，例如 `1.1.15`
- `confirm`：严格填写 `RELEASE`

工作流会确认：

- 当前运行基于 `main`
- `clash/version.yaml` 包含对应版本
- 测试和规则审计通过
- 同名 tag 尚不存在

通过后才会创建 `v<version>` tag 和 GitHub Release。扩展脚本版本、服务器版本文件、网页固定脚本地址和文档必须在发布 PR 中先同步完成。

## 哪些事情不会自动完成

以下动作需要维护者人工处理：

- 审核并合并自动生成的规则 PR
- 审核域名的官方证据、共享 CDN 风险和实际用途
- 决定是否发布新版本
- 在发布前检查客户端兼容性和变更范围
- 处理抓取失败、规则审计失败或外部链接异常
- 删除机器人分支前确认没有开放 PR、未提交工作或仍在使用

当前没有启用定时自动删除机器人分支，避免误删仍被使用的分支。

## 手动运行

维护者可以在仓库的 **Actions** 页面选择工作流并点击 **Run workflow**。推荐顺序：

1. 先运行 `PR Quality Gate` 或打开测试 PR。
2. 需要更新规则时运行同步工作流。
3. 发现正式规则异常时运行 `Scheduled Rules Security Audit`。
4. 发布时最后运行 `Release validation and publish`，并填写 `RELEASE`。

## 权限和安全边界

- 工作流使用固定 commit SHA 的第三方 Action。
- 默认采用最小权限；规则同步只读仓库并使用 PR 权限，质量检查只读仓库。
- Issue、标题、正文、域名和 URL 均视为不可信输入。
- 不在日志、文档或提交中保存 Token、密码、Cookie、私钥或其他凭据。
- 自动化生成的内容必须通过测试、规则审计和人工 PR 审核后才能进入 `main`。

相关文件：

- 工作流：`.github/workflows/`
- 生成器：`scripts/auto_update_ai.py`
- 规则审计：`scripts/rules_audit.py`
- 变更报告：`scripts/rules_change_report.py`
- 官方证据检查：`scripts/verify_official_evidence.py`
- 更新手册：[`update-guide.md`](./update-guide.md)
