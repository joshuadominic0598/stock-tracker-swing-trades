"""Private local connections. Secrets never enter workspace exports or browser responses."""

import copy
import json
import os
import re
import threading

from swing_signal.ai.catalog import CLOUD_MODELS, PROVIDERS, choices
from swing_signal.data import storage

LOCK = threading.Lock()
DEFAULTS = dict(
    default_provider="local",
    local_model="qwen3:8b",
    local_models=["qwen3:8b", "qwen3:14b"],
    gemini_model="gemini-3.5-flash-lite",
    gemini_tier="free",
    openai_model="gpt-5-mini",
    groq_model="openai/gpt-oss-20b",
    groq_tier="free",
)
SECRET_KEYS = ("gemini_api_key", "openai_api_key", "groq_api_key")
ENV = {k: k.upper() for k in SECRET_KEYS}
MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")

def path():
    return storage.DB_PATH.parent / "connections.json"

def _disk():
    try:
        value = json.loads(path().read_text())
    except (OSError, ValueError):
        return {}
    return (
        {k: v for k, v in value.items() if k in (*DEFAULTS, *SECRET_KEYS)}
        if isinstance(value, dict)
        else {}
    )

def read():
    return dict(
        copy.deepcopy(DEFAULTS),
        **_disk(),
        **{k: os.environ[v] for k, v in ENV.items() if os.environ.get(v)},
    )

def public():
    values = read()
    return dict(
        price_source="Yahoo Finance",
        **{k: values.get(k, v) for k, v in DEFAULTS.items()},
        **{k + "_configured": bool(values.get(k)) for k in SECRET_KEYS},
        **{k + "_from_environment": bool(os.environ.get(v)) for k, v in ENV.items()},
    )

def update(body):
    if not isinstance(body, dict):
        raise ValueError("Use a connection settings object")
    with LOCK:
        values = dict(copy.deepcopy(DEFAULTS), **_disk())
        for key in DEFAULTS:
            if key in body:
                values[key] = body[key]
        if values["default_provider"] not in PROVIDERS:
            raise ValueError("Choose Ollama, Gemini, OpenAI or Groq")
        for provider in ("gemini", "groq"):
            if values[provider + "_tier"] not in ("free", "paid"):
                raise ValueError("Choose a free or paid account plan")
        for provider in CLOUD_MODELS:
            if values[provider + "_model"] not in [
                m["id"] for m in choices(provider, values.get(provider + "_tier", "paid"))
            ]:
                raise ValueError(
                    "Choose a supported "
                    + provider.title()
                    + " model for the selected account plan"
                )
        enabled = values["local_models"]
        if (
            not isinstance(enabled, list)
            or not enabled
            or len(enabled) > 32
            or any(not isinstance(n, str) or not MODEL_NAME.fullmatch(n) for n in enabled)
        ):
            raise ValueError("Choose at least one installed Ollama chat model (maximum 32)")
        values["local_models"] = list(dict.fromkeys(enabled))
        if values["local_model"] not in values["local_models"]:
            raise ValueError("Enable the selected default Ollama model")
        for key in SECRET_KEYS:
            if body.get("clear_" + key):
                values.pop(key, None)
            elif body.get(key):
                token = str(body[key]).strip()
                if len(token) > 8192 or any(c.isspace() for c in token):
                    raise ValueError("Invalid connection credential")
                values[key] = token
        path().parent.mkdir(parents=True, exist_ok=True)
        temporary = path().with_suffix(".tmp")
        fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(values, f)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path())
    return public()
