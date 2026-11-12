from pathlib import Path
import re
from urllib.parse import urlsplit
from typing import Literal
from pydantic import Field, SecretStr, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def public_https_origin(value: str) -> str:
    """Validate an operator origin, never derived from request headers."""
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (parts.scheme != "https" or parts.port not in (None, 443)
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment
                or "?" in value or "#" in value
                or not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host)
                or host.endswith((".localhost", ".local", ".internal"))):
            raise ValueError
    except ValueError:
        raise ValueError("Configure an exact public HTTPS origin without credentials, path, query or fragment.") from None
    return "https://" + parts.netloc


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TESTAH_", env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    app_name: str = "Testah API"
    database_url: str = "sqlite:///./testah.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    environment: Literal["development", "test", "production"] = "development"
    allow_local_sample: bool = False
    agent_timeout_seconds: float = Field(default=10, ge=1, le=60)
    agent_max_response_bytes: int = Field(default=65536, ge=1024, le=1048576)
    agent_secrets: dict[str, SecretStr] = Field(default_factory=dict)
    monitor_token: SecretStr = SecretStr("")
    workspace_access_token: SecretStr = SecretStr("")
    monitor_poll_seconds: float = Field(default=.5, ge=.1, le=5)
    monitor_heartbeat_seconds: float = Field(default=10, ge=1, le=30)
    monitor_max_streams: int = Field(default=16, ge=1, le=64)
    payment_mode: Literal["simulated", "paypal_sandbox"] = "simulated"
    paypal_environment: Literal["sandbox"] = "sandbox"
    paypal_client_id: SecretStr = SecretStr("")
    paypal_client_secret: SecretStr = SecretStr("")
    paypal_api_base_url: Literal["https://api-m.sandbox.paypal.com"] = "https://api-m.sandbox.paypal.com"
    # Blank selects the authenticated Sandbox app's own merchant, bound on creation.
    paypal_merchant_id: str = Field(default="", max_length=32, pattern=r"^[A-Z0-9]*$")
    paypal_timeout_seconds: float = Field(default=10, ge=1, le=30)
    paypal_retries: int = Field(default=1, ge=0, le=2)
    paypal_callback_base_url: str = "http://127.0.0.1:8000"
    paypal_approval_wait_seconds: int = Field(default=600, ge=10, le=1800)
    payment_operator_token: SecretStr = SecretStr("")
    execution_duration_seconds: int = Field(default=120, ge=1, le=3600)
    execution_max_turns: int = Field(default=30, ge=1, le=40)
    execution_max_tool_calls: int = Field(default=25, ge=1, le=40)
    execution_max_identical_calls: int = Field(default=3, ge=1, le=10)
    execution_max_http_requests: int = Field(default=30, ge=1, le=40)
    execution_max_message_responses: int = Field(default=3, ge=1, le=10)
    rai_provider: Literal["mock", "openai", "gemini"] = "mock"
    rai_model: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9_.:-]*$")
    rai_api_key: SecretStr = SecretStr("")
    rai_timeout_seconds: float = Field(default=20, ge=1, le=60)
    rai_max_output_tokens: int = Field(default=3000, ge=256, le=8000)
    rai_max_response_bytes: int = Field(default=131072, ge=4096, le=262144)
    rai_retries: int = Field(default=1, ge=0, le=2)
    rai_repair_attempts: int = Field(default=1, ge=0, le=1)
    rai_generation_seconds: int = Field(default=60, ge=5, le=180)
    rai_max_generation_workers: int = Field(default=2, ge=1, le=4)
    rai_max_examiner_messages: int = Field(default=6, ge=1, le=10)

    @model_validator(mode="after")
    def local_sample_is_development_only(self):
        if self.allow_local_sample and self.environment != "development":
            raise ValueError("Local sample connections are allowed only in development.")
        for configured_token in (self.monitor_token, self.payment_operator_token, self.workspace_access_token):
            token = configured_token.get_secret_value()
            if token and (not 32 <= len(token) <= 512 or any(not 33 <= ord(c) <= 126 for c in token)):
                raise ValueError("Operator tokens must be 32-512 printable ASCII characters without spaces.")
        if (self.payment_operator_token.get_secret_value() and self.monitor_token.get_secret_value()
                and self.payment_operator_token.get_secret_value() == self.monitor_token.get_secret_value()):
            raise ValueError("Payment and monitoring operator tokens must be different.")
        workspace_token = self.workspace_access_token.get_secret_value()
        if workspace_token and workspace_token in {
            self.monitor_token.get_secret_value(), self.payment_operator_token.get_secret_value()
        }:
            raise ValueError("Workspace access must use a separate token.")
        if self.paypal_callback_base_url != "http://127.0.0.1:8000":
            self.paypal_callback_base_url = public_https_origin(self.paypal_callback_base_url)
        if self.environment == "production":
            if not workspace_token:
                raise ValueError("Production requires a workspace access token.")
            if self.database_url.split(":", 1)[0] not in {"postgres", "postgresql", "postgresql+psycopg"}:
                raise ValueError("Production requires PostgreSQL persistent storage.")
            if not self.cors_origins or any(public_https_origin(origin) != origin for origin in self.cors_origins):
                raise ValueError("Production requires exact public HTTPS CORS origins without trailing slashes.")
            if self.payment_mode == "paypal_sandbox" and self.paypal_callback_base_url == "http://127.0.0.1:8000":
                raise ValueError("Production Sandbox checkout requires a public HTTPS callback origin.")
        return self
