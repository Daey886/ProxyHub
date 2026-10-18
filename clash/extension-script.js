/**
 * ProxyHub · Clash Verge / Mihomo Party 全局扩展脚本 (Global Extension Script)
 * 版本号: v1.1.5
 * 作用：
 *  1. 🖐️ 手动选择：直接选择各节点分组（包含各地区节点组、自动优选组，支持开关控制是否显示专线组）
 *  2. 各地区专线独立成组（如：🇭🇰 香港专线、🇯🇵 日本专线、⚡ 专线优选）
 *  3. 专线隔离开关 (BLOCK_IPLC: true 隔离/屏蔽；false 不隔离)
 *  4. 5 大核心业务策略组聚合选择 "🖐️ 手动选择" 与各地区节点组，纯净结构不平铺底层节点
 *  5. 自动注入全平台广告拦截 (置顶 REJECT) 与精准分流规则
 * 项目主页: https://github.com/Daey886/ProxyHub
 */

function main(config, profileName) {
  // 当前脚本版本号
  const SCRIPT_VERSION = "v1.1.5";

  // 0. 用户偏好配置项 (可在此微调)
  const SETTINGS = {
    // 【地区组专线隔离开关】：
    // true (默认): 各地区专线独立成专线组，普通地区节点组中屏蔽专线，避免日常误走高倍率/高资费；
    // false: 普通地区节点组中亦保留专线；
    // "TOTAL_BLOCK": 若设为该值，则彻底从全局所有策略组中剔除专线。
    BLOCK_IPLC: true,

    // 【🖐️ 手动选择策略组开关】：
    // true (默认): "🖐️ 手动选择" 组中包含各地区专线组与专线优选组；
    // false: "🖐️ 手动选择" 组中屏蔽所有专线组，仅展示常规地区组与常规优选组。
    MANUAL_SHOW_IPLC: true,
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
  const RULE_BASE = "https://testingcf.jsdelivr.net/gh/Daey886/ProxyHub@v1.1.5/clash";

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
  const normalRegionGroupNames = []; // 普通地区组名称
  const normalRegionAutoNames = [];  // 普通地区优选组名称
  const iplcGroupNames = [];         // 各地区专线独立组名称
  const iplcAutoNames = [];          // 各地区专线优选组名称

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
      iplcAutoNames.push(iplcAutoName);

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
      normalRegionGroupNames.push(normalGroupName);
      normalRegionAutoNames.push(normalAutoName);

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
      iplcAutoNames.push(otherIplcAuto);

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
      normalRegionGroupNames.push(otherGroupName);
      normalRegionAutoNames.push(otherAutoName);

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

  // 所有代理分组合集 (普通组 + 专线组)
  const allRegionGroups = [...normalRegionGroupNames, ...iplcGroupNames];

  // 构建 "🖐️ 手动选择" 策略组：直接选择节点组！受 MANUAL_SHOW_IPLC 开关控制是否包含专线组
  let manualGroupCandidates = [];
  if (SETTINGS.MANUAL_SHOW_IPLC) {
    // 包含普通组、专线组、普通优选组、专线优选组
    manualGroupCandidates = [
      ...normalRegionGroupNames,
      ...iplcGroupNames,
      ...normalRegionAutoNames,
      ...iplcAutoNames,
      "DIRECT"
    ];
  } else {
    // 屏蔽专线组，仅包含普通地区组和常规优选组
    manualGroupCandidates = [
      ...normalRegionGroupNames,
      ...normalRegionAutoNames,
      "DIRECT"
    ];
  }

  // 4. 构建策略组结构 (5大核心业务组聚合选择"🖐️ 手动选择"与各地区节点组)
  const customGroups = [
    // 🖐️ 手动选择：直接选择各个节点组
    {
      name: "🖐️ 手动选择",
      type: "select",
      proxies: manualGroupCandidates.length > 0 ? manualGroupCandidates : ["DIRECT"]
    },
    // 5 大核心业务策略组
    {
      name: "🤖 海外AI",
      type: "select",
      proxies: [
        "🖐️ 手动选择",
        ...allRegionGroups.filter(n => !n.includes("香港")),
        "DIRECT"
      ]
    },
    {
      name: "🇨🇳 国产AI",
      type: "select",
      proxies: ["DIRECT", "🖐️ 手动选择", ...allRegionGroups]
    },
    {
      name: "🎬 国际流媒体",
      type: "select",
      proxies: ["🖐️ 手动选择", ...allRegionGroups, "DIRECT"]
    },
    {
      name: "💬 社交网络",
      type: "select",
      proxies: ["🖐️ 手动选择", ...allRegionGroups, "DIRECT"]
    },
    {
      name: "💻 开发者服务",
      type: "select",
      proxies: ["🖐️ 手动选择", ...allRegionGroups, "DIRECT"]
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
