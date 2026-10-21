import unittest
import subprocess
import json
import os

class TestClashExtensionScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 动态定位项目根目录中的 clash/extension-script.js，避免硬编码绝对路径
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.script_path = os.path.join(repo_root, "clash", "extension-script.js")

    def run_script_with_config(self, config_obj):
        js_code = f"""
        const fs = require('fs');
        const content = fs.readFileSync({json.dumps(self.script_path)}, 'utf8');
        eval(content + '; global.main = main;');
        const input = {json.dumps(config_obj)};
        const output = global.main(input);
        console.log(JSON.stringify(output));
        """
        res = subprocess.run(["node", "-e", js_code], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Node execution failed: {res.stderr}")
        return json.loads(res.stdout)

    def test_syntax_and_basic_execution(self):
        # 1. 验证 node --check
        res = subprocess.run(["node", "--check", self.script_path], capture_output=True)
        self.assertEqual(res.returncode, 0)

    def test_private_and_cn_rules_present(self):
        config = {
            "proxies": [
                {"name": "🇭🇰 香港 01", "type": "ss", "server": "1.1.1.1", "port": 1000},
                {"name": "🇺🇸 美国 01", "type": "ss", "server": "2.2.2.2", "port": 2000}
            ]
        }
        res = self.run_script_with_config(config)
        rules = res.get("rules", [])
        
        # 验证局域网直连规则存在
        self.assertTrue(any("GEOIP,LAN" in r for r in rules))
        self.assertTrue(any("IP-CIDR,192.168.0.0/16" in r for r in rules))
        # 验证国内直连规则存在
        self.assertTrue(any("GEOSITE,CN" in r for r in rules))
        self.assertTrue(any("GEOIP,CN" in r for r in rules))
        # 验证漏网之鱼在最后
        self.assertEqual(rules[-1], "MATCH,🐟 漏网之鱼")

    def test_version_fallback_when_offline(self):
        # 测试在完全没有节点或离线状态下，版本策略组拥有本地直接代理兜底，不会报错且不存在自循环依赖
        config = {"proxies": []}
        res = self.run_script_with_config(config)
        version_group = next(g for g in res["proxy-groups"] if "当前版本" in g["name"])
        self.assertIn("🖥️ 当前版本：v1.1.15", version_group.get("proxies", []))
        self.assertNotIn(version_group["name"], version_group.get("proxies", []))

    def test_rule_providers_format_yaml(self):
        config = {"proxies": []}
        res = self.run_script_with_config(config)
        rps = res.get("rule-providers", {})
        for name in ["advertising", "ai-overseas", "ai-domestic", "streaming", "social", "development"]:
            self.assertIn(name, rps)
            self.assertEqual(rps[name].get("format"), "yaml")
            self.assertEqual(rps[name].get("behavior"), "domain")

    def test_direct_only_groups_contain_no_proxy_group(self):
        # 直连类策略组必须纯直连，严禁混入任何策略组名或实体节点
        config = {
            "proxies": [
                {"name": "🇭🇰 香港 01", "type": "ss", "server": "1.1.1.1", "port": 1000, "cipher": "aes-128-gcm", "password": "pwd"},
                {"name": "🇺🇸 美国 01", "type": "ss", "server": "2.2.2.2", "port": 2000, "cipher": "aes-128-gcm", "password": "pwd"}
            ]
        }
        res = self.run_script_with_config(config)
        group_names = set()
        for g in res["proxy-groups"]:
            group_names.add(g["name"])
        direct_only_groups = ["🔒 私有网络", "🏠 国内直连"]
        for g in res["proxy-groups"]:
            if g["name"] in direct_only_groups:
                self.assertEqual(g["proxies"], ["DIRECT"],
                    f"{g['name']} 直连组只能包含 DIRECT，不允许混入策略组/节点")
        # 兜底：所有直连语义组的成员都不得是其他策略组名
        for g in res["proxy-groups"]:
            if "直连" in g["name"] or "私有网络" in g["name"]:
                for member in g["proxies"]:
                    self.assertNotIn(member, group_names,
                        f"{g['name']} 直连组错误嵌套了策略组 {member}")

if __name__ == "__main__":
    unittest.main()
