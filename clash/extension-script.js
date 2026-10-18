/**
 * Clash Verge / Mihomo Party 全局扩展脚本 (Global Extension Script)
 * 作用：自动注入 2026 最新规则集 (海外AI/国产AI/流媒体等)，并生成包含避开香港(HK)非支持区的专属策略组
 * 项目主页: https://github.com/Daey886/proxy-rules
 */

function main(config, profileName) {
  // 1. 基础配置健全性校验
  if (!config) config = {};
  if (!config.proxies) config.proxies = [];
  if (!config["proxy-groups"]) config["proxy-groups"] = [];
  if (!config.rules) config.rules = [];
  if (!config["rule-providers"]) config["rule-providers"] = {};

  // 2. 注入规则集 Rule-Providers (默认走国内 CDN 加速镜像，直连无阻)
  const RULE_BASE = "https://testingcf.jsdelivr.net/gh/Daey886/proxy-rules@main/clash";

  config["rule-providers"]["ai-overseas"] = {
    type: "http",
    behavior: "domain",
    url: `${RULE_BASE}/AI-Overseas.yaml`,
    path: "./ruleset/ai-overseas.yaml",
    interval: 86400
  };

  config["rule-providers"]["ai-domestic"] = {
    type: "http",
    behavior: "domain",
    url: `${RULE_BASE}/AI-Domestic.yaml`,
    path: "./ruleset/ai-domestic.yaml",
    interval: 86400
  };

  config["rule-providers"]["streaming"] = {
    type: "http",
    behavior: "domain",
    url: `${RULE_BASE}/Streaming.yaml`,
    path: "./ruleset/streaming.yaml",
    interval: 86400
  };

  config["rule-providers"]["social"] = {
    type: "http",
    behavior: "domain",
    url: `${RULE_BASE}/Social.yaml`,
    path: "./ruleset/social.yaml",
    interval: 86400
  };

  config["rule-providers"]["development"] = {
    type: "http",
    behavior: "domain",
    url: `${RULE_BASE}/Development.yaml`,
    path: "./ruleset/development.yaml",
    interval: 86400
  };

  // 3. 构建专属策略组
  // 提取全部可用节点名称
  const allProxyNames = config.proxies.map(p => p.name);

  // 严格排除 HK / CN 等非支持区，用于海外 AI
  const nonHkProxies = config.proxies
    .filter(p => !/(香港|HK|Hong Kong|CN|China|中国|澳门|MO)/i.test(p.name))
    .map(p => p.name);

  const customGroups = [
    {
      name: "🤖 海外AI",
      type: "select",
      proxies: ["⚡ AI自动优选(避开HK)", ...nonHkProxies, "DIRECT"]
    },
    {
      name: "⚡ AI自动优选(避开HK)",
      type: "url-test",
      url: "https://api.openai.com/v1/models",
      interval: 300,
      tolerance: 50,
      filter: "(?i)^(?!.*(香港|HK|Hong Kong|CN|China|中国|澳门|MO)).*(美|US|USA|日|JP|Japan|新|SG|Singapore|英|UK)"
    },
    {
      name: "🇨🇳 国产AI",
      type: "select",
      proxies: ["DIRECT", ...allProxyNames]
    },
    {
      name: "🎬 国际流媒体",
      type: "select",
      proxies: ["GLOBAL", ...allProxyNames, "DIRECT"]
    },
    {
      name: "💬 社交网络",
      type: "select",
      proxies: ["GLOBAL", ...allProxyNames, "DIRECT"]
    },
    {
      name: "💻 开发者服务",
      type: "select",
      proxies: ["GLOBAL", ...allProxyNames, "DIRECT"]
    }
  ];

  // 插入到现有策略组头部
  config["proxy-groups"] = [...customGroups, ...config["proxy-groups"]];

  // 4. 插入分流规则 (置顶匹配)
  const customRules = [
    "RULE-SET,ai-domestic,🇨🇳 国产AI",
    "RULE-SET,ai-overseas,🤖 海外AI",
    "RULE-SET,streaming,🎬 国际流媒体",
    "RULE-SET,social,💬 社交网络",
    "RULE-SET,development,💻 开发者服务"
  ];

  config.rules = [...customRules, ...config.rules];

  return config;
}
