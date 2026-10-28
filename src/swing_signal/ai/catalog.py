"""Small, explicit text-model menus. Account access and billing remain provider-owned."""

PROVIDERS = ("local", "gemini", "openai", "groq")
LABELS = {"local": "Ollama", "gemini": "Gemini", "openai": "OpenAI", "groq": "Groq"}
CLOUD_MODELS = {
    "gemini": [
        dict(id="gemini-3.5-flash-lite", label="Gemini 3.5 Flash-Lite", free_tier=True),
        dict(id="gemini-3.8-flash", label="Gemini 3.8 Flash", free_tier=True),
        dict(
            id="gemini-3.1-pro-preview",
            label="Gemini 3.1 Pro · preview",
            free_tier=False,
        ),
        dict(
            id="gemini-2.5-flash-lite",
            label="Gemini 2.5 Flash-Lite · existing projects",
            free_tier=True,
            legacy=True,
        ),
        dict(
            id="gemini-2.5-flash",
            label="Gemini 2.5 Flash · existing projects",
            free_tier=True,
            legacy=True,
        ),
    ],
    "openai": [
        dict(id="gpt-5-mini", label="GPT-5 mini", free_tier=False),
        dict(id="gpt-4.1-mini", label="GPT-4.1 mini", free_tier=False),
        dict(id="gpt-4.1", label="GPT-4.1", free_tier=False),
    ],
    "groq": [
        dict(id="openai/gpt-oss-20b", label="GPT-OSS 20B", free_tier=True),
        dict(id="openai/gpt-oss-120b", label="GPT-OSS 120B", free_tier=True),
        dict(id="qwen/qwen3.8-27b", label="Qwen 3.8 27B · preview", free_tier=True),
    ],
}
LINKS = {
    "gemini": dict(
        key="https://aistudio.google.com/apikey",
        pricing="https://ai.google.dev/gemini-api/docs/pricing",
        usage="https://aistudio.google.com/usage",
    ),
    "openai": dict(
        key="https://platform.openai.com/api-keys",
        pricing="https://developers.openai.com/api/docs/pricing",
        usage="https://platform.openai.com/usage",
    ),
    "groq": dict(
        key="https://console.groq.com/keys",
        pricing="https://console.groq.com/docs/rate-limits",
        usage="https://console.groq.com/settings/limits",
    ),
    "local": dict(
        key="https://ollama.com/download",
        pricing="https://docs.ollama.com/api/chat",
        usage="https://ollama.com/library/qwen3",
    ),
}

def choices(provider, tier="free"):
    return [
        dict(m)
        for m in CLOUD_MODELS[provider]
        if provider != "gemini" or tier == "paid" or m["free_tier"]
    ]
