import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from app import ai_providers, intelligence, settings, storage


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def response(value):
    return Response(json.dumps(value).encode())


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = storage.DB_PATH
        storage.DB_PATH = Path(self.temp.name) / "test.sqlite3"
        storage.init()
        self.environment = patch.dict("os.environ", {}, clear=True)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        storage.DB_PATH = self.original
        self.temp.cleanup()

    def source(self):
        return dict(
            id="T1",
            as_of="2026-10-23",
            facts=dict(
                price=100,
                change=0,
                rsi=None,
                k=None,
                d=None,
                volume_ratio=None,
                distance=None,
                change_3d=None,
                change_20d=None,
            ),
        )

    def selected(self):
        return dict(
            summary=["T_CLOSE"],
            observations=["T_CLOSE"],
            counterpoints=["T_ZONE"],
            unknowns=["U_ZONE"],
            watch_next=["W_ZONE"],
        )

    def enable_keys(self):
        settings.update({p + "_api_key": "private-" + p for p in ("gemini", "openai", "groq")})

    def test_four_connections_preserve_keys_and_never_return_them(self):
        self.enable_keys()
        settings.update(
            dict(
                openai_model="gpt-4.1-mini",
                default_provider="openai",
                openai_api_key="",
            )
        )
        self.assertEqual(settings.read()["openai_api_key"], "private-openai")
        if os.name != "nt":
            self.assertEqual(settings.path().stat().st_mode & 0o777, 0o600)
        with patch("app.ai_providers.local_catalog", return_value=([], None)):
            catalog = ai_providers.models()
        self.assertEqual(set(catalog["providers"]), {"local", "gemini", "openai", "groq"})
        self.assertTrue(catalog["providers"]["openai"]["configured"])
        self.assertEqual(catalog["default_provider"], "openai")
        self.assertNotIn(
            "private-",
            json.dumps(settings.public())
            + json.dumps(catalog)
            + json.dumps(storage.rows("SELECT * FROM cache")),
        )
        settings.update(dict(clear_openai_api_key=True))
        self.assertFalse(settings.public()["openai_api_key_configured"])
        self.assertTrue(settings.public()["gemini_api_key_configured"])

    def test_environment_keys_override_disk_without_being_copied_to_it(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "environment-secret"}):
            settings.update({})
            self.assertTrue(settings.public()["openai_api_key_from_environment"])
            self.assertNotIn(
                "environment-secret",
                settings.path().read_text() + json.dumps(settings.public()),
            )
            self.assertEqual(settings.read()["openai_api_key"], "environment-secret")

    def test_free_selection_rejects_paid_only_gemini_before_any_request(self):
        self.enable_keys()
        with patch("urllib.request.urlopen") as request:
            with self.assertRaisesRegex(ValueError, "selected plan"):
                ai_providers.select_model("gemini", "gemini-3.1-pro-preview")
            request.assert_not_called()
        before = settings.path().read_bytes()
        with self.assertRaises(ValueError):
            settings.update(
                dict(gemini_model="gemini-3.1-pro-preview", gemini_api_key="replacement")
            )
        self.assertEqual(settings.path().read_bytes(), before)
        settings.update(dict(gemini_tier="paid", gemini_model="gemini-3.1-pro-preview"))
        self.assertEqual(ai_providers.select_model("gemini"), "gemini-3.1-pro-preview")
        settings.update(dict(gemini_tier="free", gemini_model="gemini-3.8-flash"))
        self.assertEqual(ai_providers.select_model("gemini"), "gemini-3.8-flash")

    def test_local_choices_exclude_embeddings_and_cloud_and_respect_enabled_models(
        self,
    ):
        raw = dict(
            models=[
                dict(name="qwen3:8b", capabilities=["completion", "thinking"]),
                dict(name="granite4:7b", capabilities=["completion"]),
                dict(name="embedding", capabilities=["embedding"]),
                dict(name="remote:cloud", capabilities=["completion"]),
                dict(
                    name="remote-hidden",
                    capabilities=["completion"],
                    remote_host="https://ollama.com",
                ),
            ]
        )
        with patch("urllib.request.urlopen", side_effect=lambda *a, **k: response(raw)):
            out = ai_providers.models()
            self.assertEqual(out["models"], ["qwen3:8b"])
            self.assertEqual(
                [m["id"] for m in out["providers"]["local"]["installed_models"]],
                ["qwen3:8b", "granite4:7b"],
            )
            settings.update(dict(local_models=["qwen3:8b", "granite4:7b"], local_model="qwen3:8b"))
            self.assertEqual(ai_providers.select_model("local", "granite4:7b"), "granite4:7b")
            with self.assertRaisesRegex(ValueError, "already installed"):
                ai_providers.select_model("local", "embedding")
        self.assertEqual(settings.read()["local_model"], "qwen3:8b")

    def test_cloud_options_still_work_when_ollama_is_offline(self):
        self.enable_keys()
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            out = ai_providers.models()
        self.assertFalse(out["available"])
        self.assertTrue(out["providers"]["groq"]["configured"])
        self.assertGreaterEqual(len(out["providers"]["groq"]["models"]), 2)

    def test_provider_and_model_are_validated_without_falling_back(self):
        self.enable_keys()
        with patch("urllib.request.urlopen") as request:
            for provider, model in [
                ("unknown", "gpt-4.1"),
                ("groq", "gpt-4.1"),
                ("openai", "openai/gpt-oss-20b"),
            ]:
                with self.assertRaises(ValueError):
                    ai_providers.select_model(provider, model)
            request.assert_not_called()

    def test_connection_checks_are_metadata_only(self):
        self.enable_keys()
        for provider, raw in [
            ("openai", dict(id="gpt-5-mini")),
            ("gemini", dict(supportedGenerationMethods=["generateContent"])),
            ("groq", dict(data=[dict(id="openai/gpt-oss-20b")])),
        ]:
            with (
                self.subTest(provider=provider),
                patch("urllib.request.urlopen", return_value=response(raw)) as call,
            ):
                result = ai_providers.check_connection(provider)
                request = call.call_args[0][0]
                self.assertTrue(result["ok"])
                self.assertIsNone(request.data)
                self.assertNotIn("private-", request.full_url)
                self.assertNotIn("responses", request.full_url)
                self.assertNotIn("completions", request.full_url)
                self.assertEqual(call.call_count, 1)

    def test_provider_errors_are_redacted_and_never_retried(self):
        self.enable_keys()
        error = urllib.error.HTTPError(
            "https://api.groq.com", 429, "provider body with private-groq", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=error) as call:
            with self.assertRaisesRegex(ValueError, "quota or rate limit") as caught:
                ai_providers.check_connection("groq")
        self.assertNotIn("private-groq", str(caught.exception))
        self.assertEqual(call.call_count, 1)

    def test_requests_identify_signaldesk_including_groq_model_checks(self):
        self.enable_keys()
        with patch(
            "urllib.request.urlopen",
            return_value=response(dict(data=[dict(id="openai/gpt-oss-20b")])),
        ) as call:
            self.assertTrue(ai_providers.check_connection("groq")["ok"])
        req = call.call_args[0][0]
        self.assertEqual(req.get_header("User-agent"), ai_providers.USER_AGENT)
        self.assertEqual(req.get_header("Accept"), "application/json")
        self.assertNotIn("private-groq", req.full_url)

    def test_network_and_model_permission_errors_are_distinguished_without_echoing_body(
        self,
    ):
        self.enable_keys()
        cases = [
            (
                dict(
                    error_code=1010,
                    error_name="browser_signature_banned",
                    detail="private-groq",
                ),
                "network protection",
            ),
            (
                dict(error=dict(code="model_permission_blocked_org", message="private-groq")),
                "organization admin",
            ),
            (
                dict(error=dict(code="model_permission_blocked_project", message="private-groq")),
                "project admin",
            ),
        ]
        for body, expected in cases:
            error = urllib.error.HTTPError(
                "https://api.groq.com",
                403,
                "Forbidden",
                {},
                io.BytesIO(json.dumps(body).encode()),
            )
            with (
                self.subTest(expected=expected),
                patch("urllib.request.urlopen", side_effect=error) as call,
            ):
                with self.assertRaisesRegex(ValueError, expected) as caught:
                    ai_providers.check_connection("groq")
                self.assertNotIn("private-groq", str(caught.exception))
                self.assertEqual(call.call_count, 1)

    def test_openai_uses_responses_selected_model_and_validates_fact_ids(self):
        self.enable_keys()
        raw = dict(
            status="completed",
            output=[
                dict(
                    type="message",
                    content=[dict(type="output_text", text=json.dumps(self.selected()))],
                )
            ],
            usage=dict(input_tokens=120, output_tokens=40),
        )
        with (
            patch("app.intelligence.evidence_pack", return_value=[self.source()]),
            patch("urllib.request.urlopen", return_value=response(raw)) as call,
        ):
            out = intelligence.generate(
                dict(symbol="HCG", name="HCG", market="NSE"),
                "gpt-4.1-mini",
                provider="openai",
            )
        request = call.call_args[0][0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-openai")
        self.assertFalse(body["store"])
        self.assertEqual(body["model"], "gpt-4.1-mini")
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertNotIn("temperature", body)
        self.assertNotIn("reasoning", body)
        self.assertEqual(out["provider"], "openai")
        self.assertEqual(out["model"], "gpt-4.1-mini")
        self.assertEqual(out["usage"]["input_tokens"], 120)
        self.assertIn("100.00", out["brief"]["summary"]["text"])
        self.assertEqual(storage.cache_get("ai:HCG:1d")["value"]["provider"], "openai")

    def test_groq_uses_its_own_endpoint_with_structured_outputs(self):
        self.enable_keys()
        raw = dict(
            choices=[
                dict(
                    message=dict(content=json.dumps(self.selected())),
                    finish_reason="stop",
                )
            ]
        )
        with (
            patch("app.intelligence.evidence_pack", return_value=[self.source()]),
            patch("urllib.request.urlopen", return_value=response(raw)) as call,
        ):
            out = intelligence.generate(
                dict(symbol="HCG", name="HCG", market="NSE"),
                "openai/gpt-oss-120b",
                provider="groq",
            )
        request = call.call_args[0][0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-groq")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(body["model"], "openai/gpt-oss-120b")
        self.assertEqual(out["provider"], "groq")

    def test_invalid_fact_or_incomplete_response_cannot_replace_saved_analysis(self):
        self.enable_keys()
        storage.cache_set("ai:HCG:1d", dict(keep="existing"), "2026-10-23T00:00:00Z")
        selected = self.selected()
        selected["summary"] = ["INVENTED_PRICE"]
        cases = [
            dict(status="incomplete", output=[]),
            dict(
                status="completed",
                output=[dict(type="message", content=[dict(type="refusal")])],
            ),
            dict(
                status="completed",
                output=[
                    dict(
                        type="message",
                        content=[dict(type="output_text", text=json.dumps(selected))],
                    )
                ],
            ),
        ]
        for raw in cases:
            with (
                patch("app.intelligence.evidence_pack", return_value=[self.source()]),
                patch("urllib.request.urlopen", return_value=response(raw)) as call,
            ):
                with self.assertRaises(ValueError):
                    intelligence.generate(
                        dict(symbol="HCG", name="HCG", market="NSE"),
                        "gpt-5-mini",
                        provider="openai",
                    )
            self.assertEqual(call.call_count, 1)
            self.assertEqual(storage.cache_get("ai:HCG:1d")["value"], dict(keep="existing"))

    def test_non_thinking_local_models_do_not_receive_unsupported_thinking_controls(
        self,
    ):
        with patch(
            "urllib.request.urlopen",
            return_value=response(dict(message=dict(content="{}"))),
        ) as call:
            ai_providers.complete("local", "granite4:7b", "system", "prompt", {})
        self.assertNotIn("think", json.loads(call.call_args[0][0].data))


if __name__ == "__main__":
    unittest.main()
