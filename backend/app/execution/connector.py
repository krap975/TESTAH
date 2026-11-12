"""One bounded protocol exchange; never executes tools or retries a POST."""
import json
import math
from uuid import uuid4
import anyio
import httpx
from fastapi import Request
from pydantic import ValidationError
from app.core.config import Settings
from app.core.domain_errors import ServiceError
from app.execution.network import (LOCAL_SAMPLE_URL, DestinationError, pinned_request_url,
                                    resolve_public, validate_external_url)
from app.models.agent import Agent
from app.schemas.protocol import AgentRequest, AgentResponse, response_adapter

class ConnectorError(ServiceError):
    pass

ERRORS = {
    "timeout": (504, "The agent did not respond within the configured timeout."),
    "unreachable": (502, "The agent endpoint could not be reached over a verified connection."),
    "dns_error": (502, "The agent hostname could not be resolved."),
    "destination_blocked": (400, "The agent destination is blocked by network policy."),
    "redirect_rejected": (502, "Agent redirects are not allowed. Register the final HTTPS endpoint."),
    "authentication_rejected": (502, "The agent rejected the configured authentication (401 or 403)."),
    "agent_http_error": (502, "The agent returned an unsuccessful HTTP status."),
    "response_too_large": (502, "The agent response exceeded the configured size limit."),
    "invalid_protocol": (502, "The agent returned an invalid or mismatched protocol response."),
    "secret_unavailable": (400, "The configured server-side authentication secret is unavailable."),
    "local_sample_disabled": (400, "Enable the local sample explicitly in development to test this agent."),
}

def failure(code: str) -> ConnectorError:
    status, message = ERRORS[code]
    return ConnectorError(status, code, message)

def finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite number")
    return result

def reject_duplicate_keys(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result

class AgentConnector:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    async def exchange(self, agent: Agent, payload: AgentRequest) -> AgentResponse:
        try:
            # Includes DNS and the complete streaming exchange, so a trickled
            # response cannot extend the per-read timeout indefinitely.
            with anyio.fail_after(self.settings.agent_timeout_seconds):
                return await self._exchange(agent, payload)
        except (TimeoutError, httpx.TimeoutException):
            raise failure("timeout") from None
        except httpx.HTTPError:
            raise failure("unreachable") from None
        except DestinationError as exc:
            raise failure(str(exc) if str(exc) in ERRORS else "destination_blocked") from None

    async def _exchange(self, agent: Agent, payload: AgentRequest) -> AgentResponse:
        headers = {"Accept": "application/json", "Content-Type": "application/json", "Accept-Encoding": "identity"}
        extensions = {}
        if agent.connection_mode == "local_sample":
            if (self.settings.environment != "development" or not self.settings.allow_local_sample
                    or agent.endpoint_url != LOCAL_SAMPLE_URL):
                raise failure("local_sample_disabled")
            url = httpx.URL(LOCAL_SAMPLE_URL)
        else:
            endpoint = validate_external_url(agent.endpoint_url)
            address = await resolve_public(httpx.URL(endpoint).host)
            url, host_headers, extensions = pinned_request_url(endpoint, address)
            headers.update(host_headers)
        if agent.auth_secret_key:
            secret = self.settings.agent_secrets.get(agent.auth_secret_key)
            if not secret or not secret.get_secret_value() or any(ord(c) < 32 or ord(c) > 126 for c in secret.get_secret_value()):
                raise failure("secret_unavailable")
            headers[agent.auth_header_name] = secret.get_secret_value()
        body = payload.model_dump_json().encode("utf-8")
        if len(body) > 65536:
            raise ServiceError(400, "request_too_large", "Protocol request exceeds 64 KiB.")
        transport = self.transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False,
                                    timeout=self.settings.agent_timeout_seconds) as client:
            async with client.stream("POST", url, content=body, headers=headers, extensions=extensions) as response:
                if 300 <= response.status_code < 400:
                    raise failure("redirect_rejected")
                if response.status_code in (401, 403):
                    raise failure("authentication_rejected")
                if not 200 <= response.status_code < 300:
                    raise failure("agent_http_error")
                if (response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"
                        or response.headers.get("content-encoding", "identity").lower() != "identity"):
                    raise failure("invalid_protocol")
                limit = self.settings.agent_max_response_bytes
                declared = response.headers.get("content-length")
                if declared and (not declared.isascii() or not declared.isdecimal() or len(declared) > 10 or int(declared) > limit):
                    raise failure("response_too_large")
                content = bytearray()
                async for chunk in response.aiter_raw(chunk_size=4096):
                    content.extend(chunk)
                    if len(content) > limit:
                        raise failure("response_too_large")
        try:
            parsed = json.loads(content, object_pairs_hook=reject_duplicate_keys, parse_float=finite_float,
                                parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
            result = response_adapter.validate_python(parsed)
            if result.request_id != payload.request_id or result.session_id != payload.session_id:
                raise ValueError()
            if result.type == "tool_call" and result.tool_call.name not in {tool.name for tool in payload.available_tools}:
                raise ValueError()
            return result
        except (ValidationError, ValueError, RecursionError, UnicodeError):
            raise failure("invalid_protocol") from None

def connection_probe(mode: str = "message") -> AgentRequest:
    return AgentRequest(
        protocol_version="1.0", request_id=str(uuid4()), session_id="connection-test-" + str(uuid4()),
        message={"role": "user", "content": "Please confirm compatibility with the Testah candidate protocol."},
        available_tools=[{"name": "test_echo", "description": "Protocol-only example; never executed.",
                          "input_schema": {"type": "object", "properties": {"text": {"type": "string"}},
                                           "required": ["text"], "additionalProperties": False}}],
        context={"purpose": "connection_test", "sample_response_mode": mode},
    )

def get_connector(request: Request) -> AgentConnector:
    return AgentConnector(request.app.state.settings)

