# 🌐 ProxyHub · 多平台代理规则集 (Proxy Rules)

[![GitHub Pages](https://img.shields.io/badge/Web%20Portal-Online-blue?style=flat-square&logo=github)](https://daey886.github.io/proxy-rules/)
[![Platform](https://img.shields.io/badge/Platform-Loon%20%7C%20QX%20%7C%20Surge%20%7C%20Shadowrocket%20%7C%20Clash-success?style=flat-square)](https://daey886.github.io/proxy-rules/)
[![License](https://img.shields.io/badge/License-MIT-orange?style=flat-square)](LICENSE)

> 一站式开箱即用的分流规则集，专为 **Loon**、**Quantumult X**、**Surge**、**Shadowrocket (小火箭)**、**Clash / Mihomo** 设计。支持 **NSRingo 风格 URL Scheme 一键唤醒导入**。

👉 **一键导入中心（Web Portal）**：**[https://daey886.github.io/proxy-rules/](https://daey886.github.io/proxy-rules/)**

---

## ✨ 核心特性

- **🤖 2026 最新海外 AI 矩阵**：聚合收录 OpenAI (ChatGPT/Sora)、Anthropic (Claude)、Google DeepMind (Gemini/Antigravity)、Cursor、Perplexity、Mistral、xAI、Groq 等主流 API，精准走代理。
- **🇨🇳 国产 AI 强制直连 (DIRECT)**：涵盖 DeepSeek、阿里百炼 (DashScope)、智谱 (GLM)、Kimi、豆包、MiniMax、硅基流动等，避免国内模型走代理导致封号或网络劣化。
- **📱 全平台 URL Scheme 一键导入**：直接在 Web 端点击按钮唤起客户端完成安装。
- **🔒 纯净开源**：零私有数据、零内网域名、零无效外链，适合全公开订阅使用。

---

## 📂 仓库目录结构

| 目录 | 适用客户端 | 规则格式 |
| :--- | :--- | :--- |
| [`/loon/`](./loon/) | **Loon** | 远程规则集 (`.list`) |
| [`/qx/`](./qx/) | **Quantumult X** | 远程分流代码片段 (`.snippet`) |
| [`/surge/`](./surge/) | **Surge** | 模块规则集 (`.list`) |
| [`/shadowrocket/`](./shadowrocket/) | **Shadowrocket** | 规则集 (`.list`) |
| [`/clash/`](./clash/) | **Clash / Mihomo** | Rule-Provider (`.yaml`) |
| [`/ssr/`](./ssr/) | **SSR / Shadowsocks** | ACL 分流规则 (`proxy.acl`) |

---

## 🛠 客户端手动配置指南

### 1. Quantumult X (`[filter_remote]` 节点)
```ini
https://raw.githubusercontent.com/Daey886/proxy-rules/main/qx/AI-Overseas.snippet, tag=海外AI, force-remote-dns=true, update-interval=86400, opt-parser=false
https://raw.githubusercontent.com/Daey886/proxy-rules/main/qx/AI-Domestic.snippet, tag=国产AI直连, force-remote-dns=false, update-interval=86400, opt-parser=false
https://raw.githubusercontent.com/Daey886/proxy-rules/main/qx/Streaming.snippet, tag=流媒体, force-remote-dns=false, update-interval=86400, opt-parser=false
```

### 2. Loon (`[Remote Rule]` 节点)
```ini
https://raw.githubusercontent.com/Daey886/proxy-rules/main/loon/AI-Overseas.list, policy=海外AI, tag=海外AI, enabled=true
https://raw.githubusercontent.com/Daey886/proxy-rules/main/loon/AI-Domestic.list, policy=DIRECT, tag=国产AI直连, enabled=true
https://raw.githubusercontent.com/Daey886/proxy-rules/main/loon/Streaming.list, policy=流媒体, tag=流媒体, enabled=true
```

### 3. Surge (`[Rule]` 节点)
```ini
RULE-SET,https://raw.githubusercontent.com/Daey886/proxy-rules/main/surge/AI-Overseas.list,海外AI
RULE-SET,https://raw.githubusercontent.com/Daey886/proxy-rules/main/surge/AI-Domestic.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/Daey886/proxy-rules/main/surge/Streaming.list,流媒体
```

### 4. Clash / Mihomo (`rule-providers` 与策略组配置)

> **💡 关键提示**：OpenAI、Anthropic Claude、Google Gemini 等海外 AI 平台**严格不支持中国大陆与中国香港 (HK) 节点**访问。建议在策略组中使用正则过滤，自动排除香港节点：

```yaml
proxy-groups:
  # 海外 AI 专属策略组：自动排除香港(HK)、中国(CN)等不支持区域
  - name: 海外AI
    type: select
    proxies:
      - 自动选择(AI可用区)
      - 美国节点
      - 日本节点
      - 新加坡节点
      - DIRECT

  # 自动优选（过滤非支持区）
  - name: 自动选择(AI可用区)
    type: url-test
    url: https://api.openai.com/v1/models
    interval: 300
    tolerance: 50
    filter: "(?i)^(?!.*(香港|HK|Hong Kong|CN|China|中国|澳门|MO)).*(美|US|USA|日|JP|Japan|新|SG|Singapore|英|UK)"

rule-providers:
  ai-overseas:
    type: http
    behavior: domain
    url: "https://raw.githubusercontent.com/Daey886/proxy-rules/main/clash/AI-Overseas.yaml"
    path: ./ruleset/ai-overseas.yaml
    interval: 86400
  ai-domestic:
    type: http
    behavior: domain
    url: "https://raw.githubusercontent.com/Daey886/proxy-rules/main/clash/AI-Domestic.yaml"
    path: ./ruleset/ai-domestic.yaml
    interval: 86400

rules:
  - RULE-SET,ai-overseas,海外AI
  - RULE-SET,ai-domestic,DIRECT
  - GEOIP,CN,DIRECT
  - MATCH,兜底策略
```

---

## 📝 平台收录与动态更新日志 (Changelog)

> 每次 GitHub Actions 自动爬取到新 AI 平台或规则更新时，均会自动记录在此：

| 日期 | 变动类型 | 涉及平台 / 厂商 | 分流策略 | 详细说明 |
| :--- | :--- | :--- | :--- | :--- |
| `2026-10-18` | 🚀 **初始化上线** | LMSYS & OpenRouter 头部全矩阵 | `海外AI` / `DIRECT` | 自动抓取并初始化收录 89+ 全球 AI 活跃机构与提供商 |
| `2026-10-18` | 🤖 **AI 矩阵扩充** | OpenAI, Claude, Antigravity, Cursor, Perplexity 等 | `海外AI (代理)` | 覆盖 2026 最新代码/大模型 API，并加入规避 HK 提示 |
| `2026-10-18` | 🇨🇳 **国产大模型** | DeepSeek, 通义千问, 智谱GLM, Kimi, 豆包, MiniMax 等 | `DIRECT (直连)` | 强制直连保证响应延迟，防止代理出口风控与误伤 |
| `2026-10-18` | 🌐 **Web Portal** | Loon, Surge, QX, Shadowrocket, Clash | `多端一键导入` | 部署 GitHub Pages 静态安装主页，实现 NSRingo 级一键唤醒 |

---

## 📄 License
MIT © [Daey886](https://github.com/Daey886)
