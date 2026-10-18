import urllib.request
import json
import re
import os

# 已知厂商/模型提供商与域名的权威映射映射表（涵盖海外与国内）
PROVIDER_DOMAINS = {
    # 境外平台（需代理，避开非支持区）
    "overseas": {
        "openai": ["openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com", "sora.com"],
        "anthropic": ["anthropic.com", "claude.ai"],
        "google": [
            "generativelanguage.googleapis.com", "ai.google.dev", "aistudio.google.com",
            "aiplatform.googleapis.com", "gemini.google.com", "antigravity.google", "antigravity.com"
        ],
        "meta": ["llama.meta.com", "meta.ai"],
        "mistral": ["mistral.ai", "codestral.mistral.ai"],
        "xai": ["x.ai", "grok.com"],
        "cursor": ["cursor.com", "cursor.sh", "cursorapi.com"],
        "perplexity": ["perplexity.ai"],
        "groq": ["groq.com"],
        "together": ["together.ai", "together.xyz"],
        "fireworks": ["fireworks.ai"],
        "cerebras": ["cerebras.ai"],
        "replicate": ["replicate.com"],
        "cohere": ["cohere.com"],
        "voyage": ["voyageai.com"],
        "openrouter": ["openrouter.ai"],
        "huggingface": ["huggingface.co"],
        "poe": ["poe.com"],
        "midjourney": ["midjourney.com"],
        "elevenlabs": ["elevenlabs.io"],
        "runway": ["runwayml.com"],
        "suno": ["suno.com", "suno.ai"],
        "kling-overseas": ["klingai.com"],
        "ideogram": ["ideogram.ai"],
    },
    # 境内平台（强制 DIRECT 本地直连）
    "domestic": {
        "deepseek": ["deepseek.com", "deepseek.cn"],
        "qwen": ["aliyun.com", "dashscope.aliyuncs.com", "tongyi.ai", "qwenlm.ai"],
        "alibaba": ["aliyun.com", "dashscope.aliyuncs.com"],
        "zhipu": ["zhipuai.cn", "bigmodel.cn", "open.bigmodel.cn", "chatglm.cn"],
        "moonshot": ["moonshot.cn", "kimi.ai", "kimi.com"],
        "doubao": ["doubao.com", "volcengine.com"],
        "bytedance": ["doubao.com", "volcengine.com"],
        "minimax": ["minimax.chat", "minimaxi.com", "hailuoai.com"],
        "stepfun": ["stepfun.com", "jieyue.ai"],
        "baichuan": ["baichuan-ai.com"],
        "baidu": ["baidu.com", "yiyan.baidu.com", "bcebos.com", "baidubce.com"],
        "lingyi": ["01.ai", "lingyiwanwu.com"],
        "siliconflow": ["siliconflow.cn", "siliconflow.com"],
        "internlm": ["internlm.org", "opencompass.org.cn"],
        "baai": ["baai.ac.cn"],
        "sensetime": ["sensetime.com", "sensecore.cn"],
        "tencent": ["hunyuan.tencent.com", "tencentmind.com"],
        "kuaishou": ["klingai.cn"],
    }
}

def fetch_openrouter_providers():
    url = "https://openrouter.ai/api/v1/models"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    found_orgs = set()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            for item in data.get("data", []):
                mid = item.get("id", "")
                if "/" in mid:
                    org = mid.split("/")[0].lower()
                    found_orgs.add(org)
    except Exception as e:
        print(f"Fetch OpenRouter error: {e}")
    return found_orgs

def fetch_hf_trending():
    url = "https://huggingface.co/api/models?sort=downloads&direction=-1&limit=50"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    found_orgs = set()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            for item in data:
                mid = item.get("id", "")
                if "/" in mid:
                    org = mid.split("/")[0].lower()
                    found_orgs.add(org)
    except Exception as e:
        print(f"Fetch HF trending error: {e}")
    return found_orgs

def main():
    print("Scraping AI Leaderboard & Trending Platforms...")
    or_orgs = fetch_openrouter_providers()
    hf_orgs = fetch_hf_trending()
    all_active_orgs = or_orgs | hf_orgs
    print(f"Discovered {len(all_active_orgs)} active model publishers.")

    # 汇总规则列表
    overseas_domains = set()
    domestic_domains = set()

    for org, domains in PROVIDER_DOMAINS["overseas"].items():
        overseas_domains.update(domains)

    for org, domains in PROVIDER_DOMAINS["domestic"].items():
        domestic_domains.update(domains)

    # 动态匹配探测
    for org in all_active_orgs:
        matched = False
        for k in PROVIDER_DOMAINS["domestic"]:
            if k in org:
                matched = True
                domestic_domains.update(PROVIDER_DOMAINS["domestic"][k])
                break
        if not matched:
            for k in PROVIDER_DOMAINS["overseas"]:
                if k in org:
                    matched = True
                    overseas_domains.update(PROVIDER_DOMAINS["overseas"][k])
                    break

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # 生成规则：合并仓库中已有域名，禁止自动同步删除人工维护内容。
    def load_existing_domains(name):
        existing = set()
        candidates = [
            ("clash", f"{name}.yaml"), ("loon", f"{name}.list"),
            ("surge", f"{name}.list"), ("shadowrocket", f"{name}.list"),
            ("qx", f"{name}.snippet"), ("v2ray", f"{name}.txt"),
        ]
        for directory, filename in candidates:
            path = os.path.join(base_dir, directory, filename)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # 支持 DOMAIN-SUFFIX,foo、HOST-SUFFIX,foo、domain:foo 和 Clash +.foo。
                    if line.startswith("+."):
                        value = line[2:].strip("'\"")
                    elif line.startswith(("DOMAIN-SUFFIX,", "HOST-SUFFIX,")):
                        value = line.split(",", 1)[1].strip()
                    elif line.startswith("domain:"):
                        value = line.split(":", 1)[1].strip()
                    else:
                        continue
                    if value and "." in value and not value.startswith("#"):
                        existing.add(value.lower())
        return existing

    def build_lists(name, domains, is_direct=False):
        domains = sorted(set(domains) | load_existing_domains(name))
        # 1. Loon / Surge / Shadowrocket
        lines = [f"# {name} Ruleset (Auto-Generated)", f"# Total Domains: {len(domains)}\n"]
        for d in domains:
            lines.append(f"DOMAIN-SUFFIX,{d}")
        
        with open(os.path.join(base_dir, "loon", f"{name}.list"), "w") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(base_dir, "surge", f"{name}.list"), "w") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(base_dir, "shadowrocket", f"{name}.list"), "w") as f:
            f.write("\n".join(lines) + "\n")

        # 2. QX
        qx_lines = [f"# {name} Ruleset for Quantumult X\n"]
        for d in domains:
            qx_lines.append(f"HOST-SUFFIX,{d}")
        with open(os.path.join(base_dir, "qx", f"{name}.snippet"), "w") as f:
            f.write("\n".join(qx_lines) + "\n")

        # 3. Clash
        payload = ["payload:"]
        for d in domains:
            payload.append(f"  - '+.{d}'")
        with open(os.path.join(base_dir, "clash", f"{name}.yaml"), "w") as f:
            f.write("\n".join(payload) + "\n")

        # 4. V2Ray / Xray / v2rayN / v2rayNG
        v2_lines = [f"# {name} Ruleset for V2Ray / Xray / v2rayN / v2rayNG"]
        for d in domains:
            v2_lines.append(f"domain:{d}")
        with open(os.path.join(base_dir, "v2ray", f"{name}.txt"), "w") as f:
            f.write("\n".join(v2_lines) + "\n")

    # Snapshot the effective rule domain set before writing, so the changelog only
    # records real additions and does not create a daily no-op entry.
    before_domains = {
        "AI-Overseas": load_existing_domains("AI-Overseas"),
        "AI-Domestic": load_existing_domains("AI-Domestic"),
    }
    build_lists("AI-Overseas", overseas_domains, is_direct=False)
    build_lists("AI-Domestic", domestic_domains, is_direct=True)
    after_domains = {
        "AI-Overseas": set(overseas_domains) | before_domains["AI-Overseas"],
        "AI-Domestic": set(domestic_domains) | before_domains["AI-Domestic"],
    }
    print("Rules updated successfully from AI leaderboards.")

    # Keep the repository's platform registry and changelog in sync with the
    # generated rules.  The workflow stages README.md explicitly.
    readme_path = os.path.join(base_dir, "README.md")
    if os.path.exists(readme_path):
        from datetime import datetime, timezone
        new_domains = {
            name: sorted(after_domains[name] - before_domains[name])
            for name in after_domains
        }
        matched_platforms = sorted({
            provider
            for category in PROVIDER_DOMAINS.values()
            for provider in category
            if any(provider in org for org in all_active_orgs)
        })
        if any(new_domains.values()) or matched_platforms:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            platforms = ", ".join(matched_platforms) or "AI leaderboard providers"
            added = sum(len(values) for values in new_domains.values())
            row = (
                f"| `{today}` | 🤖 **自动同步** | {platforms} | "
                f"`海外AI` / `DIRECT` | 收录 {len(matched_platforms)} 个匹配平台，"
                f"新增 {added} 个域名，重复域名已去重 |\n"
            )
            with open(readme_path, encoding="utf-8") as f:
                readme = f.read()
            # Idempotency: one generated entry per UTC date.
            date_marker = f"| `{today}` | 🤖 **自动同步** |"
            if date_marker not in readme:
                marker = "| :--- | :--- | :--- | :--- | :--- |\n"
                if marker not in readme:
                    raise RuntimeError("README changelog table header not found")
                readme = readme.replace(marker, marker + row, 1)
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(readme)
                print(f"Changelog updated: {today}; platforms={len(matched_platforms)}, domains={added}")
            else:
                print("Changelog already contains this generated entry.")
        else:
            print("No new platforms or domains; changelog unchanged.")

if __name__ == "__main__":
    main()
