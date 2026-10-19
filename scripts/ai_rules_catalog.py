"""Provider catalogue and official source URLs used by ``scripts/auto_update_ai.py``.

The catalogue is deliberately conservative:

* Every domain listed here must be a host that the provider itself documents
  (API host in its own docs / SDK, or the host the public web app is served
  from).  Domains that merely *look* related are not accepted.
* A domain may only appear in one routing class.  The classes are
  ``overseas`` (route through the proxy) and ``domestic`` (force DIRECT).
* Shared CDN roots (``googleapis.com``, ``gstatic.com``, ``cloudflare.com``,
  ...) are not routed as a whole.  A suffix rule on them would drag unrelated
  Google/Cloudflare traffic through the proxy and can break logins, so only
  concrete service hosts (``generativelanguage.googleapis.com``,
  ``lh3.googleusercontent.com``) are kept.
  :data:`SHARED_CDN_ROOTS` lists the roots that are rejected on sight.  A
  *sub-domain* of such a root is allowed only when it is listed in the
  catalogue **and** recorded in :data:`OFFICIAL_SOURCES`, i.e. somebody has
  written down why that exact host is needed.  Anything else (a leftover
  ``foo.amazonaws.com`` in a ruleset) is a guess and is rejected, because
  :data:`ALLOWED_SHARED_ROOT_SUBDOMAINS` is derived from the catalogue.
* ``sync_sources`` are *discovery* sources.  They are fetched read-only to
  learn which publishers exist; the publisher slug taken from these APIs is
  never turned into a domain.  Turning ``openai`` into ``openai.ai`` /
  ``openai.com`` would be an unsupported guess (several real publishers do
  not own the obvious slug), so it is not done.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Official sources (documentation / public API endpoints)
# ---------------------------------------------------------------------------

#: Read-only discovery endpoints.  ``kind`` tells the fetch layer how to parse.
#: These are official, public, unauthenticated endpoints of the respective
#: platform, so no scraping of HTML documentation is required.
SYNC_SOURCES = (
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/models",
        "kind": "openrouter_models",
        "official": "https://openrouter.ai/docs",
    },
    {
        "name": "huggingface",
        "url": "https://huggingface.co/api/models?sort=downloads&direction=-1&limit=100",
        "kind": "huggingface_models",
        "official": "https://huggingface.co/docs/hub/api",
    },
)

#: Human-readable provenance for every curated official host.  Used by the
#: audit report and by ``tests/test_auto_update_ai.py`` so that a future edit
#: cannot silently add a host nobody can trace back to a vendor statement.
OFFICIAL_SOURCES = {
    # OpenAI
    "openai.com": "OpenAI API host (api.openai.com) and platform.openai.com",
    "chatgpt.com": "ChatGPT web app host",
    "oaistatic.com": "ChatGPT static assets (official CDN)",
    "oaiusercontent.com": "ChatGPT uploaded files / images (official CDN)",
    "sora.com": "Sora web app host",
    # Anthropic
    "anthropic.com": "Anthropic API host (api.anthropic.com) and console",
    "claude.ai": "Claude web app host",
    "claude.com": "Claude platform / docs host (platform.claude.com)",
    # Google / Gemini
    "ai.google.dev": "Google AI / Gemini API documentation and key pages",
    "aistudio.google.com": "Google AI Studio",
    "gemini.google.com": "Gemini web app",
    "generativelanguage.googleapis.com": "Gemini API (Generative Language API) host",
    "aiplatform.googleapis.com": "Vertex AI API host (Gemini on Vertex AI)",
    "cloudcode-pa.googleapis.com": "Gemini Code Assist / Cloud Code API host",
    "daily-cloudcode-pa.googleapis.com": "Gemini Code Assist daily channel host",
    "aisandbox-pa.googleapis.com": "Google AI sandbox endpoints used by Gemini tooling",
    "oauth2.googleapis.com": "Google OAuth 2.0 token endpoint (API auth)",
    "accounts.google.com": "Google sign-in used by Gemini AI Studio / APIs",
    "apis.google.com": "Google API loader host used by Gemini web app",
    "clients1.google.com": "Google web-app API host used by Gemini web app",
    "clients2.google.com": "Google web-app API host used by Gemini web app",
    "clients4.google.com": "Google web-app API host used by Gemini web app",
    "clients6.google.com": "Google web-app API host used by Gemini web app",
    "lh3.googleusercontent.com": "Google image/asset CDN host used by Gemini responses",
    "lh4.googleusercontent.com": "Google image/asset CDN host used by Gemini responses",
    "lh5.googleusercontent.com": "Google image/asset CDN host used by Gemini responses",
    "lh6.googleusercontent.com": "Google image/asset CDN host used by Gemini responses",
    "antigravity.google": "Google Antigravity web app host",
    "antigravity.com": "Google Antigravity (documented alternate host)",
    "antigravity-unleash.goog": "Google Antigravity feature flag host (.goog)",
    # Other overseas publishers
    "llama.meta.com": "Meta Llama site",
    "meta.ai": "Meta AI web app",
    "mistral.ai": "Mistral AI platform",
    "codestral.mistral.ai": "Codestral API host",
    "x.ai": "xAI platform / API",
    "grok.com": "Grok web app",
    "cursor.com": "Cursor web app / API",
    "cursor.sh": "Cursor docs and download host",
    "cursorapi.com": "Cursor background agent API host",
    "perplexity.ai": "Perplexity web app / API",
    "groq.com": "GroqCloud API",
    "together.ai": "Together AI API",
    "together.xyz": "Together AI legacy API host",
    "fireworks.ai": "Fireworks AI API",
    "cerebras.ai": "Cerebras Inference API",
    "replicate.com": "Replicate API",
    "cohere.com": "Cohere API",
    "voyageai.com": "Voyage AI embeddings API",
    "openrouter.ai": "OpenRouter API",
    "huggingface.co": "Hugging Face Hub / Inference API",
    "router.huggingface.co": "Hugging Face Inference Providers router",
    "poe.com": "Poe web app",
    "midjourney.com": "Midjourney web app",
    "elevenlabs.io": "ElevenLabs API",
    "runwayml.com": "Runway API",
    "suno.com": "Suno web app",
    "suno.ai": "Suno web app (alternate domain)",
    "klingai.com": "Kling AI (international)",
    "ideogram.ai": "Ideogram API",
    # Domestic (DIRECT) publishers
    "deepseek.com": "DeepSeek API platform",
    "deepseek.cn": "DeepSeek China site",
    "aliyun.com": "Alibaba Cloud (DashScope parent domain)",
    "dashscope.aliyuncs.com": "Alibaba DashScope API host",
    "dashscope.aliyun.com": "Alibaba DashScope API host (alternate)",
    "tongyi.ai": "Tongyi Qianwen web app",
    "qwenlm.ai": "Qwen chat web app",
    "zhipuai.cn": "Zhipu AI (GLM)",
    "bigmodel.cn": "Zhipu BigModel platform",
    "open.bigmodel.cn": "Zhipu BigModel API host",
    "chatglm.cn": "ChatGLM web app",
    "moonshot.cn": "Moonshot AI platform",
    "kimi.ai": "Kimi web app",
    "kimi.com": "Kimi web app (alternate)",
    "doubao.com": "Doubao web app",
    "volcengine.com": "Volcengine (Doubao parent platform)",
    "minimax.chat": "MiniMax platform",
    "minimaxi.com": "MiniMax API",
    "hailuoai.com": "Hailuo AI web app",
    "stepfun.com": "StepFun API platform",
    "jieyue.ai": "StepFun Yue web app",
    "baichuan-ai.com": "Baichuan AI platform",
    "baidu.com": "Baidu (ERNIE parent domain)",
    "yiyan.baidu.com": "ERNIE Bot web app",
    "bcebos.com": "Baidu Object Storage (ERNIE assets)",
    "baidubce.com": "Baidu AI Cloud",
    "01.ai": "01.AI / Yi platform",
    "lingyiwanwu.com": "01.AI (Lingyi Wanwu) platform",
    "siliconflow.cn": "SiliconFlow API (China)",
    "siliconflow.com": "SiliconFlow API",
    "internlm.org": "InternLM project site",
    "opencompass.org.cn": "OpenCompass project site",
    "baai.ac.cn": "BAAI",
    "sensetime.com": "SenseTime",
    "sensecore.cn": "SenseTime SenseCore",
    "hunyuan.tencent.com": "Tencent Hunyuan",
    "tencentmind.com": "Tencent AI",
    "klingai.cn": "Kling AI (China)",
}

#: Publisher slug aliases observed in the sync sources.  An alias only maps a
#: slug to an *existing catalogue provider key*; it never creates a domain.
PROVIDER_ALIASES = {
    "x-ai": "xai",
    "xai": "xai",
    "alibaba": "qwen",
    "alibaba-cloud": "qwen",
    "qwen": "qwen",
    "z-ai": "zhipu",
    "zhipuai": "zhipu",
    "thudm": "zhipu",
    "01-ai": "lingyi",
    "01ai": "lingyi",
    "baai": "baai",
    "b-a-i": "baai",
    "internlm": "internlm",
    "google": "google",
    "google-gemini": "google",
    "meta-llama": "meta",
    "meta": "meta",
    "mistralai": "mistral",
    "mistral": "mistral",
    "anthropic": "anthropic",
    "openai": "openai",
    "deepseek": "deepseek",
    "deepseek-ai": "deepseek",
    "moonshotai": "moonshot",
    "moonshot": "moonshot",
    "bytedance": "bytedance",
    "bytedance-seed": "bytedance",
    "tencent": "tencent",
    "tencent-hunyuan": "tencent",
    "minimax": "minimax",
    "minimaxai": "minimax",
    "stepfun-ai": "stepfun",
    "stepfun": "stepfun",
    "baichuan": "baichuan",
    "baidu": "baidu",
    "ernie": "baidu",
    "sensenova": "sensetime",
    "sensetime": "sensetime",
    "kuaishou": "kuaishou",
    "kling": "kuaishou",
    "perplexity": "perplexity",
    "groq": "groq",
    "cohere": "cohere",
    "huggingface": "huggingface",
    "hugging-face": "huggingface",
    "openrouter": "openrouter",
    "cerebras": "cerebras",
    "voyage-ai": "voyage",
    "together": "together",
}

# ---------------------------------------------------------------------------
# Routing classes
# ---------------------------------------------------------------------------

#: Provider key -> official domains routed through the proxy.
OVERSEAS_PROVIDERS = {
    "openai": ("openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com", "sora.com"),
    "anthropic": ("anthropic.com", "claude.ai", "claude.com"),
    "google": (
        "ai.google.dev",
        "aistudio.google.com",
        "gemini.google.com",
        "generativelanguage.googleapis.com",
        "aiplatform.googleapis.com",
        "cloudcode-pa.googleapis.com",
        "daily-cloudcode-pa.googleapis.com",
        "aisandbox-pa.googleapis.com",
        "oauth2.googleapis.com",
        "accounts.google.com",
        "apis.google.com",
        "clients1.google.com",
        "clients2.google.com",
        "clients4.google.com",
        "clients6.google.com",
        "lh3.googleusercontent.com",
        "lh4.googleusercontent.com",
        "lh5.googleusercontent.com",
        "lh6.googleusercontent.com",
        "antigravity.google",
        "antigravity.com",
        "antigravity-unleash.goog",
    ),
    "meta": ("llama.meta.com", "meta.ai"),
    "mistral": ("mistral.ai", "codestral.mistral.ai"),
    "xai": ("x.ai", "grok.com"),
    "cursor": ("cursor.com", "cursor.sh", "cursorapi.com"),
    "perplexity": ("perplexity.ai",),
    "groq": ("groq.com",),
    "together": ("together.ai", "together.xyz"),
    "fireworks": ("fireworks.ai",),
    "cerebras": ("cerebras.ai",),
    "replicate": ("replicate.com",),
    "cohere": ("cohere.com",),
    "voyage": ("voyageai.com",),
    "openrouter": ("openrouter.ai",),
    "huggingface": ("huggingface.co", "router.huggingface.co"),
    "poe": ("poe.com",),
    "midjourney": ("midjourney.com",),
    "elevenlabs": ("elevenlabs.io",),
    "runway": ("runwayml.com",),
    "suno": ("suno.com", "suno.ai"),
    "kling-overseas": ("klingai.com",),
    "ideogram": ("ideogram.ai",),
}

#: Provider key -> official domains forced DIRECT (never proxied).
DOMESTIC_PROVIDERS = {
    "deepseek": ("deepseek.com", "deepseek.cn"),
    "qwen": ("aliyun.com", "dashscope.aliyuncs.com", "dashscope.aliyun.com", "tongyi.ai", "qwenlm.ai"),
    "alibaba": ("aliyun.com", "dashscope.aliyuncs.com"),
    "zhipu": ("zhipuai.cn", "bigmodel.cn", "open.bigmodel.cn", "chatglm.cn"),
    "moonshot": ("moonshot.cn", "kimi.ai", "kimi.com"),
    "doubao": ("doubao.com", "volcengine.com"),
    "bytedance": ("doubao.com", "volcengine.com"),
    "minimax": ("minimax.chat", "minimaxi.com", "hailuoai.com"),
    "stepfun": ("stepfun.com", "jieyue.ai"),
    "baichuan": ("baichuan-ai.com",),
    "baidu": ("baidu.com", "yiyan.baidu.com", "bcebos.com", "baidubce.com"),
    "lingyi": ("01.ai", "lingyiwanwu.com"),
    "siliconflow": ("siliconflow.cn", "siliconflow.com"),
    "internlm": ("internlm.org", "opencompass.org.cn"),
    "baai": ("baai.ac.cn",),
    "sensetime": ("sensetime.com", "sensecore.cn"),
    "tencent": ("hunyuan.tencent.com", "tencentmind.com"),
    "kuaishou": ("klingai.cn",),
}

#: Backwards-compatible view of the catalogue (``{"overseas": {...}, "domestic": {...}}``).
PROVIDER_DOMAINS = {"overseas": OVERSEAS_PROVIDERS, "domestic": DOMESTIC_PROVIDERS}

#: Shared infrastructure roots.  A ``DOMAIN-SUFFIX`` rule on one of these
#: (or an unaudited sub-domain of one) would proxy / force-DIRECT unrelated
#: traffic, so such entries are removed from generated rulesets.
SHARED_CDN_ROOTS = frozenset(
    {
        "google.com",
        "googleapis.com",
        "googleusercontent.com",
        "gstatic.com",
        "googlevideo.com",
        "gvt1.com",
        "goog",
        "cloudflare.com",
        "akamai.net",
        "amazonaws.com",
        "azureedge.net",
        "jsdelivr.net",
        "githubusercontent.com",
        "aliyuncs.com",
    }
)


def _under_shared_root(domain: str) -> bool:
    """True when ``domain`` *is* a shared root or lives directly below one."""
    return any(domain == root or domain.endswith("." + root) for root in SHARED_CDN_ROOTS)


#: Audited exceptions: concrete service hosts living under a shared root.
#: Derived from the catalogue so it cannot drift from it.  A host qualifies
#: only if it is (a) not a shared root itself, (b) listed as an official
#: overseas/domestic host and (c) documented in :data:`OFFICIAL_SOURCES`.
#: Adding a host therefore requires editing the catalogue *twice* on purpose
#: (value + provenance) before a suffix rule on it may be generated.
SHARED_ROOT_EXCEPTIONS = frozenset(
    domain
    for domains in (*OVERSEAS_PROVIDERS.values(), *DOMESTIC_PROVIDERS.values())
    for domain in domains
    if domain in OFFICIAL_SOURCES
    and _under_shared_root(domain)
    and domain not in SHARED_CDN_ROOTS
)


def shared_root_violation(domain: str) -> str | None:
    """Return a human-readable reason when ``domain`` must not be routed."""
    if domain in SHARED_CDN_ROOTS:
        return f"{domain!r} is a shared infrastructure root and must not carry a suffix rule"
    if _under_shared_root(domain) and domain not in SHARED_ROOT_EXCEPTIONS:
        root = next(r for r in SHARED_CDN_ROOTS if domain.endswith("." + r))
        return (
            f"{domain!r} is an unaudited sub-domain of the shared root {root!r} without an audited source; "
            "add it to the catalogue with an official-source note (OFFICIAL_SOURCES) first"
        )
    return None
