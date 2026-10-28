"""Provider-specific transports; fixed endpoints, explicit selection, no automatic fallback."""

import json
import urllib.error
import urllib.request

from swing_signal.ai import settings
from swing_signal.ai.catalog import CLOUD_MODELS, LABELS, LINKS, PROVIDERS, choices

OLLAMA = "http://127.0.0.1:11434"
USER_AGENT = "SignalDesk/2.1 (+local desktop research app)"

def request_json(url, body=None, headers=None, timeout=180, provider="local"):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = {
            401: "API key was rejected",
            403: "account or model access was denied",
            404: "selected model is unavailable",
            429: "quota or rate limit reached; check your provider account",
            400: "request or selected model was rejected",
        }.get(exc.code, "service request failed")
        # Classify known errors without exposing arbitrary provider text or credentials.
        try:
            error_body = json.loads(exc.read(8192)) if exc.fp is not None else {}
        except (OSError, ValueError, AttributeError, TypeError):
            error_body = {}
        if not isinstance(error_body, dict):
            error_body = {}
        error = error_body.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        if exc.code == 403:
            if (
                error_body.get("error_code") == 1010
                or error_body.get("error_name") == "browser_signature_banned"
            ):
                detail = "request blocked by the provider’s network protection before model access could be checked. Use the updated app; repeated blocks need provider support"
            elif provider == "groq" and code == "model_permission_blocked_org":
                detail = "selected model is blocked by your Groq organization. An organization admin can enable it in Groq Console → Settings → Limits"
            elif provider == "groq" and code == "model_permission_blocked_project":
                detail = "selected model is blocked by your Groq project. A project admin can enable it in Groq Console → Project settings → Limits"
        raise ValueError(
            f"{LABELS[provider]}: {detail} (HTTP {exc.code}). No other provider or model was tried."
        ) from None
    except (OSError, ValueError):
        raise ValueError(
            LABELS[provider]
            + ": could not read a complete response. Check the connection and try again. No fallback was used."
        ) from None

def local_catalog():
    try:
        raw = request_json(OLLAMA + "/api/tags", timeout=3)
        models = []
        for entry in raw.get("models", []):
            name = entry.get("name", "")
            caps = entry.get("capabilities")
            remote = (
                entry.get("remote_host")
                or entry.get("remote_model")
                or (entry.get("details") or {}).get("remote_host")
                or name.endswith(":cloud")
            )
            if remote or not settings.MODEL_NAME.fullmatch(name):
                continue
            # Older Ollama versions omit capabilities in /tags; embedding names stay excluded.
            if (
                caps is not None
                and "completion" not in caps
                or caps is None
                and "embed" in name.lower()
            ):
                continue
            models.append(
                dict(
                    id=name,
                    label="Qwen3 8B · default" if name == "qwen3:8b" else name,
                    size=entry.get("size"),
                    capabilities=caps or [],
                    free_tier=True,
                )
            )
        models.sort(key=lambda m: (m["id"] != "qwen3:8b", m["id"] != "qwen3:14b", m["id"]))
        return models, None
    except ValueError as exc:
        return [], str(exc)

def models():
    config = settings.read()
    installed, error = local_catalog()
    enabled = set(config["local_models"])
    selected = [m for m in installed if m["id"] in enabled]
    providers = {
        "local": dict(
            id="local",
            label="Ollama",
            configured=bool(selected),
            models=selected,
            installed_models=installed,
            default_model=config["local_model"],
            tier="local",
            reason=error
            or (
                "Choose enabled chat models below."
                if installed
                else "No local chat models found. Install Qwen3 8B in Ollama."
            ),
        ),
    }
    for provider in CLOUD_MODELS:
        providers[provider] = dict(
            id=provider,
            label=LABELS[provider],
            configured=bool(config.get(provider + "_api_key")),
            models=choices(provider, config.get(provider + "_tier", "paid")),
            all_models=[dict(m) for m in CLOUD_MODELS[provider]],
            default_model=config[provider + "_model"],
            tier=config.get(provider + "_tier", "paid"),
            reason="A saved key is not a verified connection; use Check connection.",
        )
    for provider, value in providers.items():
        value["links"] = LINKS[provider]
    return dict(
        providers=providers,
        default_provider=config["default_provider"],
        available=bool(selected),
        models=[m["id"] for m in selected],
        reason=providers["local"]["reason"],
        gemini_available=providers["gemini"]["configured"],
        gemini_model=config["gemini_model"],
    )

def select_model(provider, model="", catalog=None):
    if provider not in PROVIDERS:
        raise ValueError("Choose Ollama, Gemini, OpenAI or Groq analysis")
    config = settings.read()
    model = model or config[provider + "_model"]
    if provider == "local":
        available = (catalog if catalog is not None else models())["models"]
        if model not in available:
            raise ValueError("Choose an enabled chat model already installed in Ollama")
    else:
        if not config.get(provider + "_api_key"):
            raise ValueError("Add a " + LABELS[provider] + " API key in Data & AI connections")
        if model not in [
            m["id"] for m in choices(provider, config.get(provider + "_tier", "paid"))
        ]:
            raise ValueError(
                "Choose an available " + LABELS[provider] + " model for your selected plan"
            )
    return model

def check_connection(provider, model=""):
    model = select_model(provider, model)
    config = settings.read()
    if provider == "local":
        pass  # select_model already checks the installed, enabled catalog.
    elif provider == "gemini":
        raw = request_json(
            "https://generativelanguage.googleapis.com/v1beta/models/" + model,
            headers={"x-goog-api-key": config["gemini_api_key"]},
            timeout=15,
            provider=provider,
        )
        if "generateContent" not in raw.get("supportedGenerationMethods", []):
            raise ValueError("This Gemini model does not support text generation")
    elif provider == "openai":
        raw = request_json(
            "https://api.openai.com/v1/models/" + model,
            headers={"Authorization": "Bearer " + config["openai_api_key"]},
            timeout=15,
            provider=provider,
        )
        if raw.get("id") != model:
            raise ValueError("OpenAI did not confirm this model")
    else:
        raw = request_json(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": "Bearer " + config["groq_api_key"]},
            timeout=15,
            provider=provider,
        )
        if not any(m.get("id") == model and m.get("active", True) for m in raw.get("data", [])):
            raise ValueError("This model is unavailable in your Groq account")
    return dict(
        ok=True,
        provider=provider,
        model=model,
        message="Model connection checked. No analysis was generated. "
        + (
            "Runs on this Mac."
            if provider == "local"
            else "Billing plan, remaining quota and generation access cannot be verified from this check."
        ),
    )

def complete(provider, model, system, prompt, schema):
    config = settings.read()
    messages = [dict(role="system", content=system), dict(role="user", content=prompt)]
    if provider == "local":
        payload = dict(
            model=model,
            stream=False,
            format=schema,
            keep_alive="5m",
            messages=messages,
            options=dict(temperature=0, num_ctx=16384, num_predict=2048),
        )
        # Do not send think=false to models that do not support Ollama thinking controls.
        if any(x in model.lower() for x in ("qwen3", "deepseek-r1", "gpt-oss")):
            payload["think"] = False
        raw = request_json(OLLAMA + "/api/chat", payload, provider=provider)
        return (
            raw["message"]["content"],
            raw.get("prompt_eval_count"),
            raw.get("eval_count"),
        )
    if provider == "gemini":
        payload = dict(
            systemInstruction=dict(parts=[dict(text=system)]),
            contents=[dict(role="user", parts=[dict(text=prompt)])],
            generationConfig=dict(
                temperature=0,
                maxOutputTokens=4096,
                responseMimeType="application/json",
                responseJsonSchema=schema,
            ),
        )
        raw = request_json(
            "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent",
            payload,
            {"x-goog-api-key": config["gemini_api_key"]},
            provider=provider,
        )
        candidate = raw["candidates"][0]
        if candidate.get("finishReason") not in (None, "STOP"):
            raise ValueError("Gemini analysis was incomplete or blocked; nothing was saved")
        text = "".join(
            p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought")
        )
        usage = raw.get("usageMetadata", {})
        return text, usage.get("promptTokenCount"), usage.get("candidatesTokenCount")
    if provider == "openai":
        payload = dict(
            model=model,
            store=False,
            instructions=system,
            input=prompt,
            max_output_tokens=4096,
            text=dict(
                format=dict(
                    type="json_schema",
                    name="stock_evidence",
                    strict=True,
                    schema=schema,
                )
            ),
        )
        if model.startswith("gpt-5"):
            payload["reasoning"] = dict(effort="minimal")
        raw = request_json(
            "https://api.openai.com/v1/responses",
            payload,
            {"Authorization": "Bearer " + config["openai_api_key"]},
            provider=provider,
        )
        if raw.get("status") not in (None, "completed"):
            raise ValueError("OpenAI analysis was incomplete; nothing was saved")
        content = [
            part
            for item in raw.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
        ]
        if any(part.get("type") == "refusal" for part in content):
            raise ValueError("OpenAI declined this analysis; nothing was saved")
        text = "".join(
            part.get("text", "") for part in content if part.get("type") == "output_text"
        )
        usage = raw.get("usage", {})
        return text, usage.get("input_tokens"), usage.get("output_tokens")
    payload = dict(
        model=model,
        messages=messages,
        stream=False,
        temperature=0,
        max_completion_tokens=2048,
        response_format=dict(
            type="json_schema",
            json_schema=dict(name="stock_evidence", strict=True, schema=schema),
        ),
    )
    if model.startswith("openai/gpt-oss-"):
        payload["reasoning_effort"] = "low"
    raw = request_json(
        "https://api.groq.com/openai/v1/chat/completions",
        payload,
        {"Authorization": "Bearer " + config["groq_api_key"]},
        provider=provider,
    )
    choice = raw["choices"][0]
    if choice.get("finish_reason") not in (None, "stop"):
        raise ValueError("Groq analysis was incomplete; nothing was saved")
    usage = raw.get("usage", {})
    return (
        choice["message"]["content"],
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
    )
