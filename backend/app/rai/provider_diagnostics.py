"""Explicit development checks executed in the same process and adapter as RAI jobs."""
import os
import sys
from time import perf_counter

from app.core.config import BACKEND_ROOT, Settings
from app.events.store import sanitize
from app.rai.errors import failure_message
from app.rai.provider import GeminiProvider, ProviderError, provider_config, provider_metadata, secret_values


class ProviderDiagnostics:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.running = False
        self.runtime = {
            "pid": os.getpid(), "parent_pid": os.getppid(), "python_executable": sys.executable,
            "env_file": str(BACKEND_ROOT / ".env"),
            "declared_network_disabled": os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "").lower() in {"1", "true"},
            "process_override_names": sorted(name for name in os.environ if name.upper().startswith("TESTAH_RAI_")),
            "environment_proxy_inheritance": False, "redirects_enabled": False, "tls_verification": True,
        }

    async def run(self) -> dict:
        settings = self.settings
        result = {
            **provider_metadata(provider_config(settings)), "runtime": self.runtime,
            "key_configured": bool(settings.rai_api_key.get_secret_value() and not settings.rai_api_key.get_secret_value().startswith("REPLACE_")),
            "limits": {name: getattr(settings, name) for name in (
                "rai_timeout_seconds", "rai_generation_seconds", "rai_retries", "rai_repair_attempts",
                "rai_max_output_tokens", "rai_max_response_bytes", "rai_max_generation_workers")},
            "check_limits": {"connectivity_seconds": min(10, settings.rai_timeout_seconds),
                             "smoke_seconds": settings.rai_timeout_seconds, "smoke_max_output_tokens": 256, "retries": 0},
            "connectivity": {"status": "skipped", "code": "gemini_not_selected", "latency_ms": None},
            "smoke_test": {"status": "skipped", "code": "gemini_not_selected", "latency_ms": None},
        }
        if settings.rai_provider != "gemini":
            return sanitize(result, secret_values(settings))
        # This is the sole Gemini adapter, with deliberately smaller diagnostic costs.
        provider = GeminiProvider(settings.model_copy(update={"rai_retries": 0, "rai_max_output_tokens": 256}))
        start = perf_counter()
        try:
            reached = await provider.check_connectivity()
            result["connectivity"] = {"status": "ok", "code": "https_reached", **reached,
                                      "latency_ms": round((perf_counter() - start) * 1000, 3)}
        except ProviderError as exc:
            result["connectivity"] = self.failure(exc, start)
            result["smoke_test"] = {"status": "skipped", "code": "connectivity_failed", "latency_ms": None}
            return sanitize(result, secret_values(settings))
        start = perf_counter()
        try:
            output = await provider.generate("diagnostic", "Return exactly the JSON object {\"ok\":true}.", {},
                {"type": "object", "properties": {"ok": {"type": "boolean", "enum": [True]}},
                 "required": ["ok"], "additionalProperties": False})
            if output != {"ok": True} or type(output.get("ok")) is not bool:
                raise ProviderError("invalid_model_output")
            result["smoke_test"] = {"status": "ok", "code": "authenticated_generation_succeeded",
                                    "latency_ms": round((perf_counter() - start) * 1000, 3)}
        except ProviderError as exc:
            result["smoke_test"] = self.failure(exc, start)
        return sanitize(result, secret_values(settings))

    @staticmethod
    def failure(exc: ProviderError, start: float) -> dict:
        return {"status": "failed", "code": exc.code, "message": failure_message(exc.code),
                "http_status": exc.http_status, "latency_ms": round((perf_counter() - start) * 1000, 3)}
