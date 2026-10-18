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

### 4. Clash / Mihomo (`rule-providers` 节点)
```yaml
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

## 📄 License
MIT © [Daey886](https://github.com/Daey886)
