/**
 * Clash Verge / Mihomo Party 全局扩展脚本 (Global Extension Script)
 * 作用：自动注入 2026 最新规则集 (海外AI/国产AI/流媒体等)，并生成包含避开香港(HK)非支持区的专属策略组
 * 项目主页: https://github.com/Daey886/ProxyHub
 */

function main(config, profileName) {
  // 1. 基础配置健全性校验
  if (!config) config = {};
  if (!config.proxies) config.proxies = [];
  if (!config["proxy-groups"]) config["proxy-groups"] = [];
  if (!config.rules) config.rules = [];
  if (!config["rule-providers"]) config["rule-providers"] = {};

  // 2. 注入规则集 Rule-Providers (默认走国内 CDN 加速镜像，直连无阻)
  const RULE_BASE = "https://testingcf.jsdelivr.net/gh/Daey886/ProxyHub@main/clash";

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

  config["rule-providers"]["advertising"] = {
    type: "http",
    behavior: "domain",
    url: `${RULE_BASE}/Advertising.yaml`,
    path: "./ruleset/advertising.yaml",
    interval: 86400
  };

  // 3. 动态提取节点并按国家/地区智能分组
  const allProxyNames = config.proxies.map(p => p.name);

  // 地区正则匹配规则
  const regions = [
    { name: "🇭🇰 香港节点", reg: /(香港|HK|Hong Kong|HongKong)/i },
    { name: "🇯🇵 日本节点", reg: /(日本|JP|Japan|Tokyo|Osaka)/i },
    { name: "🇺🇸 美国节点", reg: /(美国|US|USA|United States|America)/i },
    { name: "🇸🇬 新加坡节点", reg: /(新加坡|SG|Singapore|狮城)/i },
    { name: "🇹🇼 台湾节点", reg: /(台湾|TW|Taiwan|Taipei)/i },
    { name: "🇬🇧 英国节点", reg: /(英国|UK|United Kingdom|London)/i },
    { name: "🇩🇪 德国节点", reg: /(德国|DE|Germany|Frankfurt)/i },
    { name: "🇰🇷 韩国节点", reg: /(韩国|KR|Korea|Seoul)/i }
  ];

  // 为每个地区生成对应的节点列表和自动优选组
  const regionSelectGroups = [];
  const regionAutoGroups = [];
  const regionGroupNames = [];
  const matchedProxyNames = new Set();

  regions.forEach(r => {
    const matched = config.proxies.filter(p => r.reg.test(p.name)).map(p => p.name);
    if (matched.length > 0) {
      matched.forEach(name => matchedProxyNames.add(name));
      regionGroupNames.push(r.name);
      
      const autoGroupName = `⚡ ${r.name.replace("节点", "自动优选")}`;
      regionAutoGroups.push({
        name: autoGroupName,
        type: "url-test",
        url: "https://www.gstatic.com/generate_204",
        interval: 300,
        tolerance: 50,
        proxies: [...matched]
      });

      regionSelectGroups.push({
        name: r.name,
        type: "select",
        proxies: [autoGroupName, ...matched]
      });
    }
  });

  // 兜底：未被上述主流地区匹配到的其他节点 (如加拿大、澳大利亚、土耳其、阿根廷、专线等)
  const otherProxies = config.proxies
    .filter(p => !matchedProxyNames.has(p.name))
    .map(p => p.name);

  if (otherProxies.length > 0) {
    const otherGroupName = "🌐 其他节点";
    regionGroupNames.push(otherGroupName);

    const otherAutoName = "⚡ 其他自动优选";
    regionAutoGroups.push({
      name: otherAutoName,
      type: "url-test",
      url: "https://www.gstatic.com/generate_204",
      interval: 300,
      tolerance: 50,
      proxies: [...otherProxies]
    });

    regionSelectGroups.push({
      name: otherGroupName,
      type: "select",
      proxies: [otherAutoName, ...otherProxies]
    });
  }

  // 严格排除 HK / CN 等非支持区，用于海外 AI
  const nonHkProxies = config.proxies
    .filter(p => !/(香港|HK|Hong Kong|CN|China|中国|澳门|MO)/i.test(p.name))
    .map(p => p.name);

  const customGroups = [
    {
      name: "🤖 海外AI",
      type: "select",
      proxies: [
        "⚡ AI自动优选(避开HK)",
        ...regionGroupNames.filter(n => !n.includes("香港")),
        ...nonHkProxies,
        "DIRECT"
      ]
    },
    {
      name: "⚡ AI自动优选(避开HK)",
      type: "url-test",
      url: "https://api.openai.com/v1/models",
      interval: 300,
      tolerance: 50,
      proxies: nonHkProxies.length > 0 ? [...nonHkProxies] : (allProxyNames.length > 0 ? [...allProxyNames] : ["DIRECT"])
    },
    {
      name: "🇨🇳 国产AI",
      type: "select",
      proxies: ["DIRECT", ...regionGroupNames, ...allProxyNames]
    },
    {
      name: "🎬 国际流媒体",
      type: "select",
      proxies: ["GLOBAL", ...regionGroupNames, ...allProxyNames, "DIRECT"]
    },
    {
      name: "💬 社交网络",
      type: "select",
      proxies: ["GLOBAL", ...regionGroupNames, ...allProxyNames, "DIRECT"]
    },
    {
      name: "💻 开发者服务",
      type: "select",
      proxies: ["GLOBAL", ...regionGroupNames, ...allProxyNames, "DIRECT"]
    },
    {
      name: "🛑 广告拦截",
      type: "select",
      proxies: ["REJECT", "DIRECT"]
    },
    ...regionSelectGroups,
    ...regionAutoGroups
  ];

  // 插入到现有策略组头部
  config["proxy-groups"] = [...customGroups, ...config["proxy-groups"]];

  // 4. 插入分流规则 (置顶匹配)
  const customRules = [
    "RULE-SET,advertising,🛑 广告拦截",
    "RULE-SET,ai-domestic,🇨🇳 国产AI",
    "RULE-SET,ai-overseas,🤖 海外AI",
    "RULE-SET,streaming,🎬 国际流媒体",
    "RULE-SET,social,💬 社交网络",
    "RULE-SET,development,💻 开发者服务"
  ];

  config.rules = [...customRules, ...config.rules];

  return config;
}
