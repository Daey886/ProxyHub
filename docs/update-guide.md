# ProxyHub 仓库更新手册

本文用于维护 ProxyHub 的 Clash/Mihomo 全局扩展脚本、网页入口和 GitHub Release。

## 1. 文件职责

| 文件 | 用途 |
|---|---|
| `clash/extension-script.js` | Clash/Mihomo 全局扩展脚本；生成策略组和分流规则 |
| `docs/index.html` | GitHub Pages 首页和扩展脚本入口 |
| `.github/workflows/pages-healthcheck.yml` | 低频检查 GitHub Pages 是否正常 |

## 2. 版本规则

每次对外发布必须同时维护两个版本：

1. 扩展脚本中的 `SCRIPT_VERSION`
2. Git 标签和 GitHub Release

版本格式统一为 `vMAJOR.MINOR.PATCH`，例如 `v1.1.14`。

策略组中的 `📌 当前版本：...` 表示用户当前下载的扩展脚本版本。

## 3. 修改扩展脚本

编辑：

```text
clash/extension-script.js
```

修改以下内容：

```js
const SCRIPT_VERSION = "v1.1.14";
```

脚本的策略组处理原则：

- 原订阅的真实节点保留，供 ProxyHub 自动分组使用。
- 原订阅的 `proxy-groups` 全部丢弃，避免用户策略残留和重复组名。
- 原订阅的顶层 `rules` 全部丢弃，仅使用脚本生成的规则。
- 版本策略组只使用脚本注入的版本虚拟节点。
- 不要把版本虚拟节点当作真实代理节点使用。

## 4. 更新网页入口

`docs/index.html` 中的扩展脚本地址应固定到本次脚本提交，而不是使用可能缓存旧内容的 `@main`：

```text
https://testingcf.jsdelivr.net/gh/Daey886/ProxyHub@<SCRIPT_COMMIT>/clash/extension-script.js
```

网页中的更新提示、版本说明和文档链接也应同步修改。

## 5. 本地验证

提交前至少执行：

```bash
node --check clash/extension-script.js
```

还要用包含原订阅策略的测试配置验证：

- 原订阅 `proxy-groups` 不再出现在输出配置中。
- 原订阅 `rules` 不再出现在输出配置中。
- 原订阅真实节点仍然存在。
- `Proxy` 及其他脚本策略组名称唯一。
- `📌 当前版本：...` 存在。
- 输出配置包含 `MATCH` 兜底规则。

推荐使用 Clash Verge 的“测试配置”再次确认实际生成结果。

## 6. 提交和发布

按以下顺序执行：

```bash
git switch main
git pull --ff-only origin main
# 修改文件
node --check clash/extension-script.js
git diff --check
git add clash/extension-script.js docs/index.html docs/update-guide.md
git commit -m "release: v1.1.14"
git push origin main
gh release create v1.1.14 --target main \
  --title "ProxyHub v1.1.14" \
  --notes-file RELEASE_NOTES.md
```

如果项目使用 PR 流程，应先创建分支和 PR，等待检查通过后再合并；禁止直接向受保护的 `main` 推送。

发布后核对：

```bash
gh release view v1.1.14 --json tagName,name,publishedAt,isDraft,isPrerelease,targetCommitish

gh release list --limit 3 --json tagName,name,isLatest,publishedAt
```

确认：

- 标签存在并指向预期提交。
- Release 不是草稿。
- Release 不是预发布。
- 新 Release 被标记为 Latest。

## 7. 发布后回源检查

检查网页：

```bash
curl -4 -fsSL "https://daey886.github.io/ProxyHub/?v=<VERSION>"
```

检查固定脚本地址：

```bash
curl -4 -fsSL \
  "https://testingcf.jsdelivr.net/gh/Daey886/ProxyHub@<SCRIPT_COMMIT>/clash/extension-script.js" \
  | grep SCRIPT_VERSION
```

如果远程内容仍是旧版本，先确认 `main` 已更新，再使用固定提交地址；不要把缓存的 `@main` 内容当作发布结果。

## 8. 用户升级步骤

用户需要：

1. 使用网页上的最新脚本入口重新导入全局扩展脚本。
2. 重新生成或测试 Clash 配置。
3. 确认策略组中显示 `📌 当前版本：...`。

仅刷新原始代理订阅不会自动加载新的扩展脚本；扩展脚本更新后必须重新导入或重新执行。

## 9. 常见问题

### 仍然看到用户原来的策略组

检查是否实际加载了新脚本。确认脚本来源是本次提交的固定 URL，并清理 Clash Verge 的旧测试配置或重新生成配置。

### 出现 `duplicate group name`

检查输出配置的 `proxy-groups` 是否仍包含原订阅策略组，尤其是 `Proxy`。新脚本应只输出 ProxyHub 生成的策略组。

### 节点不见了

脚本只删除原订阅的策略组和规则，不应删除 `config.proxies`。如果节点确实消失，检查上游订阅内容和客户端生成配置，而不是直接修改清理逻辑。

## 10. AI 规则自动同步（`scripts/auto_update_ai.py`）

AI 分流规则由 `scripts/auto_update_ai.py` 生成，厂商与域名清单维护在
`scripts/ai_rules_catalog.py`。工作流 `.github/workflows/sync-ai-leaderboard.yml`
每小时运行一次（`0 * * * *`，UTC），也可以在 Actions 页面手动触发。

### 安全约束

- 工作流**不会直接 push 到 `main`**。改动会提交到机器人分支
  `automation/sync-ai-rules`，并以 Pull Request 形式等待人工评审后合并。
- 工作流权限为 `contents: read` + `pull-requests: write`，`checkout` 不持久化凭据。
- 抓取失败、校验失败时立即中止（退出码 2 / 3），**不会写入任何文件**，
  因此不会出现“只更新了一半”的规则集。
- 写入采用“暂存 + 原子替换 + 失败回滚”，写完后还会跨客户端做一致性校验。

### 共享 CDN 规则

`googleapis.com`、`gstatic.com`、`googleusercontent.com`、`amazonaws.com` 等
共享根域名**不允许**整段走代理（会误伤无关流量、破坏登录）。只允许具体的服务主机，
例如 `generativelanguage.googleapis.com`、`lh3.googleusercontent.com`。

允许清单由目录自动推导：某个主机要放行，必须同时满足
（1）在 `OVERSEAS_PROVIDERS` / `DOMESTIC_PROVIDERS` 中列出，
（2）在 `OFFICIAL_SOURCES` 中写了来源说明。新增域名请两处一起补。

### 本地命令

```bash
# 仅审计，不写文件；规则集不是最新时退出码为 1
python scripts/auto_update_ai.py --check --offline

# 预览将要发生的变更
python scripts/auto_update_ai.py --dry-run --offline

# 实际生成并写入，同时输出 JSON 审计报告
python scripts/auto_update_ai.py --audit-report /tmp/audit.json

# 运行测试
python -m unittest discover -s tests -v
```

## 11. 发布检查清单

- [ ] `SCRIPT_VERSION` 已更新
- [ ] `docs/index.html` 已同步
- [ ] `node --check` 通过
- [ ] 原订阅策略组已清除
- [ ] 原订阅规则已清除
- [ ] 原始节点仍存在
- [ ] 策略组名称唯一
- [ ] GitHub Pages 返回 HTTP 200
- [ ] Git 标签已创建
- [ ] GitHub Release 已发布并标记 Latest
- [ ] 固定提交脚本地址回源内容正确
