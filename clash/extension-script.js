/**
 * ProxyHub · Clash Verge / Mihomo Party 全局扩展脚本 (Global Extension Script)
 * 作用：
 *  1. 各地区专线独立成组（如：🇭🇰 香港专线、🇯🇵 日本专线、⚡ 专线优选）
 *  2. 专线隔离开关 (true: 普通地区组屏蔽专线，避免误跑高倍率；false: 普通组亦包含专线)
 *  3. 5 大核心业务策略组仅选节点分组与 Proxy，告别节点平铺堆叠
 *  4. 顶层聚合 🚀 Proxy 策略组
 *  5. 自动注入全平台广告拦截 (置顶 REJECT) 与海外 AI 智能避障 (避开 HK/国内)
 * 项目主页: https://github.com/Daey886/ProxyHub
 */

function main(config, profileName) {
  // 0. 用户偏好配置项 (可在此微调)
  const SETTINGS = {
    // 专线隔离与屏蔽开关：
    // true (默认): 各地区专线独立成专线组，普通地区节点组中屏蔽专线，避免日常误走高倍率/高资费；
    // false: 普通地区节点组中亦保留专线；
    // "TOTAL_BLOCK": 若设为该值，则彻底从全局所有策略组中剔除专线。
    BLOCK_IPLC: true,
  };

  // 1. 基础配置健全性校验
  if (!config) config = {};
  if (!config.proxies) config.proxies = [];
  if (!config["proxy-groups"]) config["proxy-groups"] = [];
  if (!config.rules) config.rules = [];
  if (!config["rule-providers"]) config["rule-providers"] = {};

  // 专线识别正则 (IPLC / IEPL / 专线 / 广港 / 沪日 / 莞港 / 深港 / 京德 / 广新 等)
  const IPLC_REG = /(IPLC|IEPL|专线|广港|沪日|莞港|深港|京德|广新|中继专线|内网互联)/i;

  const rawProxies = config.proxies;

  // 2. 注入规则集 Rule-Providers (走 ProxyHub 镜像源)
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

  // 3. 动态提取节点并按国家/地区智能分组 (常规组 + 专线独立组)
  const regions = [
    { name: "香港", icon: "🇭🇰", reg: /(香港|HK|Hong Kong|HongKong)/i },
    { name: "日本", icon: "🇯🇵", reg: /(日本|JP|Japan|Tokyo|Osaka)/i },
    { name: "美国", icon: "🇺🇸", reg: /(美国|US|USA|United States|America)/i },
    { name: "新加坡", icon: "🇸🇬", reg: /(新加坡|SG|Singapore|狮城)/i },
    { name: "台湾", icon: "🇹🇼", reg: /(台湾|TW|Taiwan|Taipei)/i },
    { name: "英国", icon: "🇬🇧", reg: /(英国|UK|United Kingdom|London)/i },
    { name: "德国", icon: "🇩🇪", reg: /(德国|DE|Germany|Frankfurt)/i },
    { name: "韩国", icon: "🇰🇷", reg: /(韩国|KR|Korea|Seoul)/i }
  ];

  const regionSelectGroups = [];
  const regionAutoGroups = [];
  const regionGroupNames = []; // 普通地区组
  const iplcGroupNames = [];   // 各地区专线独立组

  const matchedProxyNames = new Set();

  regions.forEach(r => {
    const regionAll = rawProxies.filter(p => r.reg.test(p.name)).map(p => p.name);
    if (regionAll.length === 0) return;

    regionAll.forEach(n => matchedProxyNames.add(n));

    const regionIplc = regionAll.filter(name => IPLC_REG.test(name));
    const regionNormal = regionAll.filter(name => !IPLC_REG.test(name));

    // A. 地区专属专线分组 (独立成组)
    if (SETTINGS.BLOCK_IPLC !== "TOTAL_BLOCK" && regionIplc.length > 0) {
      const iplcGroupName = `${r.icon} ${r.name}专线`;
      const iplcAutoName = `⚡ ${r.name}专线优选`;
      iplcGroupNames.push(iplcGroupName);

      regionAutoGroups.push({
        name: iplcAutoName,
        type: "url-test",
        url: "https://www.gstatic.com/generate_204",
        interval: 300,
        tolerance: 50,
        proxies: [...regionIplc]
      });

      regionSelectGroups.push({
        name: iplcGroupName,
        type: "select",
        proxies: [iplcAutoName, ...regionIplc]
      });
    }

    // B. 地区普通节点分组 (若 BLOCK_IPLC 为 true，则屏蔽专线)
    let normalProxies = [];
    if (SETTINGS.BLOCK_IPLC === true) {
      normalProxies = regionNormal.length > 0 ? regionNormal : regionAll;
    } else {
      normalProxies = regionAll;
    }

    if (normalProxies.length > 0) {
      const normalGroupName = `${r.icon} ${r.name}节点`;
      const normalAutoName = `⚡ ${r.icon} ${r.name}自动优选`;
      regionGroupNames.push(normalGroupName);

      regionAutoGroups.push({
        name: normalAutoName,
        type: "url-test",
        url: "https://www.gstatic.com/generate_204",
        interval: 300,
        tolerance: 50,
        proxies: [...normalProxies]
      });

      regionSelectGroups.push({
        name: normalGroupName,
        type: "select",
        proxies: [normalAutoName, ...normalProxies]
      });
    }
  });

  // 兜底：未被上述主流地区匹配到的其他节点
  const otherAll = rawProxies
    .filter(p => !matchedProxyNames.has(p.name))
    .map(p => p.name);

  if (otherAll.length > 0) {
    const otherIplc = otherAll.filter(n => IPLC_REG.test(n));
    const otherNormal = otherAll.filter(n => !IPLC_REG.test(n));

    // 其他专线组
    if (SETTINGS.BLOCK_IPLC !== "TOTAL_BLOCK" && otherIplc.length > 0) {
      const otherIplcGroup = "🌐 其他专线";
      const otherIplcAuto = "⚡ 其他专线优选";
      iplcGroupNames.push(otherIplcGroup);

      regionAutoGroups.push({
        name: otherIplcAuto,
        type: "url-test",
        url: "https://www.gstatic.com/generate_204",
        interval: 300,
        tolerance: 50,
        proxies: [...otherIplc]
      });

      regionSelectGroups.push({
        name: otherIplcGroup,
        type: "select",
        proxies: [otherIplcAuto, ...otherIplc]
      });
    }

    // 其他常规组
    let otherSelected = (SETTINGS.BLOCK_IPLC === true && otherNormal.length > 0) ? otherNormal : otherAll;
    if (otherSelected.length > 0) {
      const otherGroupName = "🌐 其他节点";
      const otherAutoName = "⚡ 其他自动优选";
      regionGroupNames.push(otherGroupName);

      regionAutoGroups.push({
        name: otherAutoName,
        type: "url-test",
        url: "https://www.gstatic.com/generate_204",
        interval: 300,
        tolerance: 50,
        proxies: [...otherSelected]
      });

      regionSelectGroups.push({
        name: otherGroupName,
        type: "select",
        proxies: [otherAutoName, ...otherSelected]
      });
    }
  }

  // 严格排除 HK / CN 等非支持区，用于海外 AI
  const nonHkProxies = rawProxies
    .filter(p => !/(香港|HK|Hong Kong|CN|China|中国|澳门|MO)/i.test(p.name))
    .filter(p => SETTINGS.BLOCK_IPLC === true ? !IPLC_REG.test(p.name) : true)
    .map(p => p.name);

  // 所有代理分组合集 (普通组 + 专线组)
  const allRegionGroups = [...regionGroupNames, ...iplcGroupNames];
  const allRegionAutoGroups = regionAutoGroups.map(g => g.name);

  // 全局 Proxy 分组包含的候选组
  const proxyGroupCandidates = [
    ...allRegionAutoGroups,
    ...allRegionGroups,
    "DIRECT"
  ];

  // 4. 构建策略组结构 (5大核心业务组仅选择节点分组/Proxy/DIRECT，不再堆叠平铺海量节点)
  const customGroups = [
    // 全局通用 Proxy 分组
    {
      name: "🚀 Proxy",
      type: "select",
      proxies: proxyGroupCandidates.length > 0 ? proxyGroupCandidates : ["DIRECT"]
    },
    // 5 大核心业务策略组
    {
      name: "🤖 海外AI",
      type: "select",
      proxies: [
        "⚡ AI自动优选(避开HK)",
        ...allRegionGroups.filter(n => !n.includes("香港")),
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
      proxies: nonHkProxies.length > 0 ? [...nonHkProxies] : ["DIRECT"]
    },
    {
      name: "🇨🇳 国产AI",
      type: "select",
      proxies: ["DIRECT", "🚀 Proxy", ...allRegionGroups]
    },
    {
      name: "🎬 国际流媒体",
      type: "select",
      proxies: ["🚀 Proxy", ...allRegionGroups, "DIRECT"]
    },
    {
      name: "💬 社交网络",
      type: "select",
      proxies: ["🚀 Proxy", ...allRegionGroups, "DIRECT"]
    },
    {
      name: "💻 开发者服务",
      type: "select",
      proxies: ["🚀 Proxy", ...allRegionGroups, "DIRECT"]
    },
    {
      name: "🛑 广告拦截",
      type: "select",
      proxies: ["REJECT", "DIRECT"]
    },
    // 各国家/地区独立专线组与普通节点组
    ...regionSelectGroups,
    // 各国家/地区测速优选组
    ...regionAutoGroups
  ];

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
