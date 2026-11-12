"""Scalar-only operational timing. Never record prompts, bodies or sensitive headers."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import os
import sys
from time import perf_counter
from collections.abc import Iterator

from app.core.config import BACKEND_ROOT, Settings
from app.events.store import sanitize

# Uvicorn's configured INFO handler makes these visible in the actual API process.
logger = logging.getLogger("uvicorn.error.rai")
proposal_context: ContextVar[str | None] = ContextVar("rai_proposal_id", default=None)


@contextmanager
def diagnostic_scope(proposal_id: str) -> Iterator[None]:
    token = proposal_context.set(proposal_id)
    try:
        yield
    finally:
        proposal_context.reset(token)


def timing(phase: str, elapsed_seconds: float, **fields: str | int | float | None) -> None:
    record = {"phase": phase, "elapsed_ms": round(max(0, elapsed_seconds) * 1000, 3),
              "proposal_id": proposal_context.get(), **fields}
    logger.info("RAI timing %s", json.dumps(record, sort_keys=True))


@contextmanager
def timed_phase(phase: str, **fields: str | int | float | None) -> Iterator[None]:
    start = perf_counter()
    try:
        yield
    except BaseException as exc:
        timing(phase, perf_counter() - start, outcome="interrupted", exception_type=type(exc).__name__, **fields)
        raise
    else:
        timing(phase, perf_counter() - start, outcome="completed", **fields)


def log_configuration(settings: Settings) -> None:
    names = ("rai_provider", "rai_model", "rai_timeout_seconds", "rai_generation_seconds", "rai_retries",
             "rai_repair_attempts", "rai_max_output_tokens", "rai_max_response_bytes", "rai_max_generation_workers")
    key = settings.rai_api_key.get_secret_value()
    values = {name: getattr(settings, name) for name in names}
    values.update(pid=os.getpid(), parent_pid=os.getppid(), python_executable=sys.executable,
                  env_file=str(BACKEND_ROOT / ".env"),
                  declared_network_disabled=os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "").lower() in {"1", "true"},
                  key_configured=bool(key and not key.startswith("REPLACE_")),
                  process_override_names=sorted(name for name in os.environ if name.upper().startswith("TESTAH_RAI_")))
    # The model name is operator-configurable; redact even an accidentally pasted key.
    secrets = [key, *[secret.get_secret_value() for secret in settings.agent_secrets.values()]]
    logger.info("RAI effective configuration %s", json.dumps(sanitize(values, secrets), sort_keys=True))
