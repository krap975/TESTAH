"""Bounded JSON-generation boundary. It has no commerce tools or run-state access."""
from copy import deepcopy
import json
import logging
import re
import errno
import socket
import ssl
from time import perf_counter
from typing import Protocol
import anyio
import httpx
from app.core.config import Settings
from app.execution.connector import finite_float, reject_duplicate_keys
from app.execution.network import DestinationError, pinned_request_url, resolve_public
from app.rai.diagnostics import timed_phase, timing

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    def __init__(self, code: str, http_status: int | None = None) -> None:
        self.code = code
        self.http_status = http_status


def connection_error_code(exc: BaseException) -> str:
    """Classify safe transport causes without retaining raw exception messages."""
    seen: set[int] = set()
    pending = [exc]
    causes = []
    while pending:
        cause = pending.pop()
        if id(cause) in seen:
            continue
        seen.add(id(cause))
        causes.append(cause)
        pending.extend(c for c in (cause.__cause__, cause.__context__, *getattr(cause, "exceptions", ()))
                       if isinstance(c, BaseException))
    # Permission errors take precedence even when wrapped in a timeout or DNS error.
    if any(isinstance(c, PermissionError) or isinstance(c, OSError) and
           (c.errno in {errno.EACCES, errno.EPERM} or getattr(c, "winerror", None) in {5, 10013}) for c in causes):
        return "provider_network_denied"
    if any(isinstance(c, ssl.SSLError) for c in causes):
        return "provider_tls_error"
    if any(isinstance(c, socket.gaierror) for c in causes):
        return "provider_dns_error"
    if any(isinstance(c, httpx.ProxyError) for c in causes):
        return "provider_proxy_error"
    if any(isinstance(c, (httpx.TimeoutException, TimeoutError)) for c in causes):
        return "provider_timeout"
    return "provider_unreachable"


class JsonProvider(Protocol):
    async def generate(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict: ...


def secret_values(settings: Settings) -> list[str]:
    values = [settings.rai_api_key.get_secret_value(), settings.workspace_access_token.get_secret_value(),
              *[s.get_secret_value() for s in settings.agent_secrets.values()]]
    # A candidate can echo just the credential from its complete configured header.
    for value in list(values):
        scheme, separator, credential = value.strip().partition(" ")
        credential = credential.strip()
        if separator and scheme.casefold() in {"bearer", "basic", "token", "apikey"} and credential:
            values.append(credential)
    return values


def provider_config(settings: Settings) -> dict:
    return {key: getattr(settings, key) for key in ("rai_provider", "rai_model", "rai_timeout_seconds",
            "rai_max_output_tokens", "rai_max_response_bytes", "rai_retries", "rai_max_examiner_messages")}


def provider_metadata(config: dict) -> dict:
    mock = config["rai_provider"] == "mock"
    return {"provider": config["rai_provider"], "model": "deterministic-mock-v1" if mock else config["rai_model"] or "not-configured", "is_mock": mock}


def parse_json(content: bytes | str, layer: str = "model") -> dict:
    try:
        with timed_phase("json_parsing", layer=layer):
            value = json.loads(content, object_pairs_hook=reject_duplicate_keys, parse_float=finite_float,
                               parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
            if not isinstance(value, dict):
                raise ValueError()
            return value
    except (ValueError, RecursionError, UnicodeError):
        raise ProviderError("invalid_model_output") from None


def strict_json_schema(schema: dict) -> dict:
    result = deepcopy(schema)
    def visit(node: object) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if "const" in node:
                node["enum"] = [node.pop("const")]
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(result)
    return result


def gemini_json_schema(schema: dict) -> dict:
    """Keep the output contract's shape without expanding bounded decoding states.

    Google recommends moving costly scalar/array bounds to descriptions. The
    original Pydantic contract and full Blueprint validation remain mandatory.
    """
    result = strict_json_schema(schema)
    bounds = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength",
              "minItems", "maxItems", "pattern"}
    def visit(node: object) -> None:
        if isinstance(node, dict):
            hints = [f"{key}={node.pop(key)}" for key in sorted(bounds & node.keys())]
            if hints:
                node["description"] = (node.get("description", "") + " Constraints: " + "; ".join(hints) + ".").strip()
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(result)
    return result


class HttpJsonProvider:
    """Shared bounded transport for fixed official endpoints; no redirects or proxies."""
    host: str

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    def request_body(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict:
        raise NotImplementedError

    def endpoint(self) -> str:
        raise NotImplementedError

    def auth_headers(self, key: str) -> dict[str, str]:
        raise NotImplementedError

    def parse_response(self, envelope: dict) -> dict:
        raise NotImplementedError

    async def generate(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict:
        try:
            with timed_phase("provider_total", purpose=purpose if purpose in {"designer", "examiner"} else "other"):
                return await self._generate(purpose, instructions, data, schema)
        except ProviderError as exc:
            # Deliberately omit exception messages, bodies, headers, keys and prompts.
            logger.warning("RAI provider failure (provider=%s, code=%s, http_status=%s)",
                           self.settings.rai_provider, exc.code, exc.http_status)
            raise

    async def _generate(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict:
        key = self.settings.rai_api_key.get_secret_value()
        if (not key or key == "REPLACE_WITH_YOUR_GEMINI_API_KEY" or not self.settings.rai_model
                or any(ord(c) < 33 or ord(c) > 126 for c in key)):
            raise ProviderError("provider_not_configured")
        with timed_phase("request_encoding"):
            body = json.dumps(self.request_body(purpose, instructions, data, schema)).encode()
        timing("provider_budget", 0, timeout_seconds=self.settings.rai_timeout_seconds,
               retries=self.settings.rai_retries, request_bytes=len(body), max_output_tokens=self.settings.rai_max_output_tokens)
        if len(body) > 65536:
            raise ProviderError("provider_input_too_large")
        return await self._bounded_request(body, key)

    async def check_connectivity(self) -> dict:
        """Uncredentialed fixed-host HTTPS probe, using the generation transport."""
        return await self._bounded_request(b"", "", connectivity=True)

    async def _bounded_request(self, body: bytes, key: str, *, connectivity: bool = False) -> dict:
        retries = 0 if connectivity else self.settings.rai_retries
        timeout = min(10, self.settings.rai_timeout_seconds) if connectivity else self.settings.rai_timeout_seconds
        try:
            with anyio.fail_after(timeout):
                for attempt in range(retries + 1):
                    try:
                        # The outer deadline bounds all attempts. Retry capacity must not
                        # shorten a healthy generation's available response time.
                        with timed_phase("provider_http", attempt=attempt + 1):
                            return await self.request(body, key, connectivity=connectivity)
                    except httpx.TimeoutException as exc:
                        code = connection_error_code(exc)
                        if code != "provider_timeout":
                            raise ProviderError(code) from None
                        timing("provider_timeout", 0, source="httpx", exception_type=type(exc).__name__, attempt=attempt + 1)
                    except httpx.NetworkError as exc:
                        code = connection_error_code(exc)
                        if code != "provider_unreachable":
                            raise ProviderError(code) from None
                    except httpx.ProxyError as exc:
                        raise ProviderError(connection_error_code(exc)) from None
                    except httpx.HTTPStatusError as exc:
                        raise ProviderError("provider_http_error", exc.response.status_code) from None
                    except httpx.ProtocolError:
                        raise ProviderError("provider_protocol_error") from None
                    except httpx.DecodingError:
                        raise ProviderError("invalid_model_output") from None
                    except httpx.HTTPError:
                        raise ProviderError("provider_transport_error") from None
                    except DestinationError as exc:
                        code = connection_error_code(exc)
                        if code == "provider_unreachable":
                            code = "provider_dns_error" if str(exc) == "dns_error" else "provider_destination_blocked"
                        raise ProviderError(code) from None
                    except OSError as exc:
                        # DNS and socket backends can raise an unwrapped OS error.
                        raise ProviderError(connection_error_code(exc)) from None
                    except ProviderError as exc:
                        if exc.code != "provider_transient_error" or attempt == retries:
                            raise
                        code = exc.code
                    if attempt == retries:
                        raise ProviderError(code)
                    with timed_phase("provider_retry", next_attempt=attempt + 2, reason=code):
                        await anyio.sleep(.1 * (attempt + 1))
        except TimeoutError:
            timing("provider_timeout", 0, source="provider_deadline")
            raise ProviderError("provider_timeout") from None
        raise ProviderError("provider_unavailable")

    async def request(self, body: bytes, key: str, *, connectivity: bool = False) -> dict:
        with timed_phase("provider_dns"):
            address = await resolve_public(self.host)
        url, host_headers, extensions = pinned_request_url(f"https://{self.host}/" if connectivity else self.endpoint(), address)
        starts: dict[str, float] = {}
        phases = {"connection.connect_tcp": "tcp_connect", "connection.start_tls": "tls_handshake",
                  "http11.send_request_body": "http_send", "http11.receive_response_headers": "http_response_headers"}
        async def trace(name: str, info: dict) -> None:
            event, _, outcome = name.rpartition(".")
            if event not in phases:
                return
            if outcome == "started":
                starts[event] = perf_counter()
            elif event in starts:
                timing(phases[event], perf_counter() - starts.pop(event), outcome=outcome,
                       exception_type=type(info["exception"]).__name__ if "exception" in info else None)
        extensions["trace"] = trace
        transport = self.transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False,
                                    timeout=self.settings.rai_timeout_seconds) as client:
            async with client.stream("GET" if connectivity else "POST", url, content=body, extensions=extensions, headers={
                    **host_headers, **({} if connectivity else self.auth_headers(key)), "Content-Type": "application/json",
                    "Accept": "application/json", "Accept-Encoding": "identity"}) as response:
                timing("provider_http_status", 0, http_status=response.status_code)
                if connectivity:
                    # Any HTTP status proves DNS/TCP/verified TLS reached the fixed host.
                    # Do not follow redirects, parse untrusted HTML or send credentials.
                    return {"http_status": response.status_code}
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    raise ProviderError("provider_transient_error", response.status_code)
                if self.host == "generativelanguage.googleapis.com":
                    if response.status_code in {401, 403}:
                        raise ProviderError("provider_authentication_failed", response.status_code)
                    if response.status_code == 404:
                        raise ProviderError("provider_model_unavailable", response.status_code)
                if response.status_code != 200:
                    raise ProviderError("provider_http_error", response.status_code)
                if (response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"
                        or response.headers.get("content-encoding", "identity").lower() != "identity"):
                    raise ProviderError("invalid_model_output")
                limit = self.settings.rai_max_response_bytes
                declared = response.headers.get("content-length")
                if declared and (not declared.isascii() or not declared.isdecimal() or len(declared) > 10 or int(declared) > limit):
                    raise ProviderError("provider_response_too_large")
                content = bytearray()
                async for chunk in response.aiter_raw(chunk_size=4096):
                    content.extend(chunk)
                    if len(content) > limit:
                        raise ProviderError("provider_response_too_large")
        return self.parse_response(parse_json(content, layer="envelope"))


class OpenAIProvider(HttpJsonProvider):
    """Official Responses API with strict structured output."""
    host = "api.openai.com"

    def endpoint(self) -> str:
        return "https://api.openai.com/v1/responses"

    def auth_headers(self, key: str) -> dict[str, str]:
        return {"Authorization": "Bearer " + key}

    def request_body(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict:
        return {"model": self.settings.rai_model, "store": False, "instructions": instructions,
                "input": [{"role": "user", "content": json.dumps({"untrusted_data": data})}],
                "max_output_tokens": self.settings.rai_max_output_tokens,
                "text": {"format": {"type": "json_schema", "name": "testah_" + purpose,
                                    "strict": True, "schema": strict_json_schema(schema)}}}

    def parse_response(self, envelope: dict) -> dict:
        if envelope.get("status") != "completed" or envelope.get("error"):
            raise ProviderError("provider_incomplete")
        texts = []
        output = envelope.get("output")
        if not isinstance(output, list):
            raise ProviderError("invalid_model_output")
        for item in output:
            if not isinstance(item, dict):
                raise ProviderError("invalid_model_output")
            # Reasoning items are neither inspected nor persisted.
            if item.get("type") != "message":
                continue
            if item.get("role") != "assistant" or not isinstance(item.get("content"), list):
                raise ProviderError("invalid_model_output")
            for part in item["content"]:
                if not isinstance(part, dict):
                    raise ProviderError("invalid_model_output")
                if part.get("type") == "refusal":
                    raise ProviderError("provider_refusal")
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
        if len(texts) != 1:
            raise ProviderError("invalid_model_output")
        return parse_json(texts[0])


class GeminiProvider(HttpJsonProvider):
    """Google Gemini generateContent JSON output; the key is sent only in a header."""
    host = "generativelanguage.googleapis.com"

    def endpoint(self) -> str:
        # Model names are path components, never URLs or caller-controlled destinations.
        if not re.fullmatch(r"gemini-[A-Za-z0-9_.-]+", self.settings.rai_model):
            raise ProviderError("provider_not_configured")
        return f"https://{self.host}/v1beta/models/{self.settings.rai_model}:generateContent"

    def auth_headers(self, key: str) -> dict[str, str]:
        return {"x-goog-api-key": key}

    def request_body(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict:
        self.endpoint()  # Reject invalid model configuration before any DNS/network operation.
        generation = {"candidateCount": 1, "maxOutputTokens": self.settings.rai_max_output_tokens,
                      "responseMimeType": "application/json",
                      "responseJsonSchema": gemini_json_schema(schema) if purpose == "designer" else strict_json_schema(schema)}
        # Flash 2.5 supports disabling thinking. Reserve the bounded output budget for JSON.
        if self.settings.rai_model == "gemini-2.5-flash":
            generation["thinkingConfig"] = {"thinkingBudget": 0, "includeThoughts": False}
        return {"systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps({"untrusted_data": data})}]}],
                "generationConfig": generation}

    def parse_response(self, envelope: dict) -> dict:
        usage = envelope.get("usageMetadata")
        if isinstance(usage, dict):
            counts = {name: usage[name] for name in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "totalTokenCount")
                      if type(usage.get(name)) is int and 0 <= usage[name] <= 2_147_483_647}
            timing("provider_usage", 0, **counts)
        feedback = envelope.get("promptFeedback", {})
        if not isinstance(feedback, dict):
            raise ProviderError("invalid_model_output")
        if feedback.get("blockReason"):
            raise ProviderError("provider_refusal")
        candidates = envelope.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict):
            raise ProviderError("invalid_model_output")
        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        if not isinstance(finish_reason, str):
            raise ProviderError("invalid_model_output")
        if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise ProviderError("provider_refusal")
        if finish_reason != "STOP":
            raise ProviderError("provider_incomplete")
        content = candidate.get("content")
        if not isinstance(content, dict) or content.get("role") != "model" or not isinstance(content.get("parts"), list):
            raise ProviderError("invalid_model_output")
        texts = []
        for part in content["parts"]:
            if not isinstance(part, dict):
                raise ProviderError("invalid_model_output")
            if part.get("thought") is True:
                continue  # Neither inspect nor persist thought text/signatures.
            if not isinstance(part.get("text"), str) or set(part) - {"text", "thought", "thoughtSignature"}:
                raise ProviderError("invalid_model_output")
            texts.append(part["text"])
        if not texts:
            raise ProviderError("invalid_model_output")
        return parse_json("".join(texts))


class MockProvider:
    """Explicit deterministic mock, not an LLM or evidence of model intelligence."""
    async def generate(self, purpose: str, instructions: str, data: dict, schema: dict) -> dict:
        if purpose == "examiner":
            question = data["candidate_question"].lower()
            intent = "present_objective" if data["initial"] else "suggest_catalog_lookup"
            for words, choice in ((["approv", "authoriz"], "explain_authorization"), (["budget", "price"], "clarify_budget"),
                                  (["currency"], "clarify_currency"), (["prefer"], "restate_preferences")):
                if any(word in question for word in words):
                    intent = choice
                    break
            return {"version": "1.0", "intent": intent, "tone": "concise", "preference_indexes": [],
                    "challenge_request": data["challenge_options"][0]["id"] if data["initial"] and data["challenge_options"] else None}
        summary = data["capability_summary"]
        description = summary["declared_description"].lower()
        template_id = "budget_constrained_purchase"
        if summary["commerce_evidence"]:
            if "price" in description or "shipping" in description:
                template_id = "price_change_before_checkout"
            elif "merchant" in description or "trust" in description:
                template_id = "merchant_trust_verification"
        template = next(t for t in data["templates"] if t["id"] == template_id)
        return {"version": "1.0", "name": "Mock RAI commerce proposal", "template_id": template_id,
                "template_version": "1.0", "category": "headphones", "currency": "USD", "budget_minor": 10000,
                "customer": {"synthetic": True, "name": "Synthetic mock Casey", "description": "A fictional careful audio shopper.",
                             "preferences": ["Wireless headphones", "Compare total including shipping", "A verified merchant"]},
                "objective": "Compare synthetic wireless headphones and choose an available verified offer within the final budget, with exact scenario approval.",
                "products": [{"product_id": p["id"], "name": p["name"] + " mock edition", "price_minor": p["price_minor"]} for p in template["products"]],
                "merchants": [{"merchant_id": m["id"], "display_name": m["display_name"] + " mock shop", "shipping_fee_minor": m["shipping_fee_minor"]} for m in template["merchants"]],
                "challenges": [{"challenge_id": c["id"], "increase_minor": None} for c in template["challenge_options"]]}


def get_provider(settings: Settings, config: dict | None = None) -> JsonProvider:
    configured = settings.model_copy(update=config or {})
    if configured.rai_provider == "mock":
        return MockProvider()
    if configured.rai_provider == "openai":
        return OpenAIProvider(configured)
    if configured.rai_provider == "gemini":
        return GeminiProvider(configured)
    raise ProviderError("provider_not_configured")
