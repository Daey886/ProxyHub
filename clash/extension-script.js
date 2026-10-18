/**
 * ProxyHub · Clash Verge / Mihomo Party 全局扩展脚本 (Global Extension Script)
 * 作用：
 *  1. 默认屏蔽专线节点 (支持开关配置)
 *  2. 5 大核心策略组仅选节点分组与 Proxy，不再平铺单个节点
 *  3. 聚合全局 Proxy 策略组
 *  4. 自动生成地区策略组及地区自动测速优选
 *  5. 自动注入广告拦截、AI避障规则
 * 项目主页: https://github.com/Daey886/ProxyHub
 */

function main(config, profileName) {
  // 0. 用户偏好配置项 (可自行在此调整)
  const SETTINGS = {
    // 是否屏蔽专线节点：默认 true 屏蔽；设为 false 则不屏蔽
    BLOCK_IPLC_IEPL: true,
  };

  // 1. 基础配置健全性校验
  if (!config) config = {};
  if (!config.proxies) config.proxies = [];
  if (!config["proxy-groups"]) config["proxy-groups"] = [];
  if (!config.rules) config.rules = [];
  if (!config["rule-providers"]) config["rule-providers"] = {};

  // 专线识别正则 (IPLC / IEPL / 专线 / 广港 / 沪日 / 莞港 / 深港 / 京德 等)
  const IPLC_REG = /(IPLC|IEPL|专线|广港|沪日|莞港|深港|京德|中继专线|内网互联)/i;

  // 根据开关过滤可用节点池
  const effectiveProxies = config.proxies.filter(p => {
    if (SETTINGS.BLOCK_IPLC_IEPL && IPLC_REG.test(p.name)) {
      return false; // 屏蔽专线
    }
    return true;
  });

  // 全量有效节点名称
  const allProxyNames = effectiveProxies.map(p => p.name);

  // 2. 注入规则集 Rule-Providers (默认走 ProxyHub 镜像源)
  const RULE_BASE = "https://testingcf.jsdelivr.net/gh/Daey886/ProxyHub/clash";

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

  const regionSelectGroups = [];
  const regionAutoGroups = [];
  const regionGroupNames = [];
  const matchedProxyNames = new Set();

  regions.forEach(r => {
    const matched = effectiveProxies.filter(p => r.reg.test(p.name)).map(p => p.name);
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

  // 兜底：未被上述主流地区匹配到的其他节点
  const otherProxies = effectiveProxies
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
  const nonHkProxies = effectiveProxies
    .filter(p => !/(香港|HK|Hong Kong|CN|China|中国|澳门|MO)/i.test(p.name))
    .map(p => p.name);

  // 所有地区自动优选组名称集合
  const allRegionAutoGroupNames = regionAutoGroups.map(g => g.name);

  // 全局 Proxy 策略组备选列表：包含各地区分组、各地区自动优选、以及全量节点与 DIRECT
  const proxyGroupCandidates = [
    ...allRegionAutoGroupNames,
    ...regionGroupNames,
    ...(allProxyNames.length > 0 ? allProxyNames : ["DIRECT"])
  ];

  // 4. 构建策略组结构 (5大核心策略组仅选择节点分组/Proxy/DIRECT，不再堆叠平铺海量节点)
  const customGroups = [
    // 全局通用 Proxy 分组
    {
      name: "🚀 Proxy",
      type: "select",
      proxies: proxyGroupCandidates.length > 0 ? proxyGroupCandidates : ["DIRECT"]
    },
    // 5 大核心业务策略组 (选择节点分组或 Proxy)
    {
      name: "🤖 海外AI",
      type: "select",
      proxies: [
        "⚡ AI自动优选(避开HK)",
        ...regionGroupNames.filter(n => !n.includes("香港")),
        "🚀 Proxy",
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
      proxies: ["DIRECT", "🚀 Proxy", ...regionGroupNames]
    },
    {
      name: "🎬 国际流媒体",
      type: "select",
      proxies: ["🚀 Proxy", ...regionGroupNames, "DIRECT"]
    },
    {
      name: "💬 社交网络",
      type: "select",
      proxies: ["🚀 Proxy", ...regionGroupNames, "DIRECT"]
    },
    {
      name: "💻 开发者服务",
      type: "select",
      proxies: ["🚀 Proxy", ...regionGroupNames, "DIRECT"]
    },
    {
      name: "🛑 广告拦截",
      type: "select",
      proxies: ["REJECT", "DIRECT"]
    },
    // 各国家/地区节点分组
    ...regionSelectGroups,
    // 各国家/地区自动优选测速组
    ...regionAutoGroups
  ];

  // 插入到现有策略组头部
  config["proxy-groups"] = [...customGroups, ...config["proxy-groups"]];

  // 5. 插入分流规则 (置顶匹配)
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
