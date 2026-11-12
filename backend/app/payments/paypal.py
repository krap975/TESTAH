"""Sandbox-only official SDK adapter with a bounded, pinned HTTPX transport.

SDK retry/logging/Requests defaults are deliberately unused. OAuth tokens stay in
memory; only fixed error categories leave this boundary. No buyer data is stored.
"""
import json
import re
from hashlib import sha256
from decimal import Decimal, InvalidOperation
from time import monotonic, time
from urllib.parse import parse_qs, urlsplit
import anyio
import httpx
from apimatic_core.http.response.http_response import HttpResponse
from apimatic_core_interfaces.client.http_client import HttpClient
from apimatic_core_interfaces.types.http_method_enum import HttpMethodEnum
from paypalserversdk.configuration import Configuration, Environment
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.models.o_auth_token import OAuthToken
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient
from paypalserversdk.api_helper import APIHelper
from app.core.config import Settings
from app.execution.network import DestinationError, pinned_request_url, resolve_public

BASE = "https://api-m.sandbox.paypal.com"
IDENTIFIER = re.compile(r"^[A-Z0-9]{1,36}$")
PLACEHOLDER_CREDENTIALS = frozenset({
    "yourpaypalsandboxclientid", "yourpaypalsandboxclientsecret", "yourpaypalsandboxmerchantid",
    "yoursandboxappclientid", "yoursandboxappclientsecret", "yoursandboxmerchantid",
    "yoursandboxbusinessmerchantid", "clientidhere", "clientsecrethere", "merchantidhere",
    "changeme", "replaceme",
})


class PayPalError(Exception):
    def __init__(self, code: str, uncertain: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.uncertain = uncertain


def credential_configured(value: str) -> bool:
    """Template placeholders are missing configuration, not usable credentials."""
    normalized = re.sub(r"[^a-z0-9]", "", value.casefold())
    return bool(normalized and normalized not in PLACEHOLDER_CREDENTIALS)


def configured(settings: Settings) -> bool:
    return bool(credential_configured(settings.paypal_client_id.get_secret_value())
                and credential_configured(settings.paypal_client_secret.get_secret_value())
                and (not settings.paypal_merchant_id or credential_configured(settings.paypal_merchant_id))
                and settings.payment_operator_token.get_secret_value())


def client_binding(settings: Settings) -> str:
    """Private stable app binding, never a merchant identifier or credential value."""
    return sha256(settings.paypal_client_id.get_secret_value().encode()).hexdigest()


def amount_value(minor: int, currency: str) -> str:
    # Blueprint 1.0 supports only these two-decimal currencies.
    if type(minor) is not int or minor <= 0 or currency not in {"USD", "EUR", "GBP"}:
        raise PayPalError("paypal_invalid_amount")
    return format(Decimal(minor) / Decimal(100), ".2f")


def matches_amount(data: dict, minor: int, currency: str) -> bool:
    try:
        value = data["value"]
        return (isinstance(value, str) and bool(re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value))
                and data["currency_code"] == currency and Decimal(value) == Decimal(minor) / 100)
    except (KeyError, TypeError, InvalidOperation):
        return False


def approval_link(order: dict) -> str | None:
    for link in order.get("links", []):
        if link.get("rel") in {"approve", "payer-action"}:
            value = link.get("href", "")
            parts = urlsplit(value)
            if (parts.scheme == "https" and parts.netloc == "www.sandbox.paypal.com"
                    and parts.path == "/checkoutnow" and not parts.fragment
                    and parse_qs(parts.query) == {"token": [order["id"]]}):
                return value
            raise PayPalError("paypal_invalid_approval_url")
    return None


class SdkTransport(HttpClient):
    def __init__(self, adapter: "PayPalSandbox") -> None:
        self.adapter = adapter

    def execute(self, request, endpoint_configuration):
        # SDK runs in an AnyIO worker thread, HTTP runs on the async task.
        return anyio.from_thread.run(self.send, request)

    async def send(self, request) -> HttpResponse:
        method = HttpMethodEnum.to_string(request.http_method)
        data = await self.adapter.request(method, request.query_url, headers=request.headers,
                                          content=request.parameters, params=request.query_parameters)
        return HttpResponse(200, "OK", {"content-type": "application/json"}, json.dumps(data), request)

    def convert_response(self, response, contains_binary_response, request):
        return response


class PayPalSandbox:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport  # Test injection only; never configurable by clients/environment.
        self._token: str | None = None
        self._expires = 0.0
        self._token_binding: str | None = None
        self._oauth_lock = anyio.Lock()

    async def request(self, method: str, url: str, **kwargs) -> dict:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "api-m.sandbox.paypal.com" or parts.fragment:
            raise PayPalError("paypal_destination_blocked")
        is_oauth = parts.path == "/v1/oauth2/token"
        headers = {key: value for key, value in (kwargs.pop("headers", {}) or {}).items() if value is not None}
        protected = bool(headers.get("PayPal-Request-Id"))
        can_retry = method == "GET" or is_oauth or protected
        try:
            # Total deadline includes DNS, all retries and the full response body.
            with anyio.fail_after(self.settings.paypal_timeout_seconds):
                for attempt in range(self.settings.paypal_retries + 1):
                    try:
                        address = await resolve_public(parts.hostname) if self.transport is None else None
                        target, host_headers, extensions = pinned_request_url(url, address) if address else (url, {}, {})
                        async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False,
                                                     timeout=self.settings.paypal_timeout_seconds) as client:
                            async with client.stream(method, target, headers={**headers, **host_headers},
                                                     extensions=extensions, **kwargs) as response:
                                body = bytearray()
                                async for chunk in response.aiter_bytes():
                                    body.extend(chunk)
                                    if len(body) > 262144:
                                        raise PayPalError("paypal_response_too_large", method == "POST" and not is_oauth)
                                status = response.status_code
                        if status in {408, 429, 500, 502, 503, 504} and can_retry and attempt < self.settings.paypal_retries:
                            await anyio.sleep(.1 * (attempt + 1))
                            continue
                        if not 200 <= status < 300:
                            # No provider text/debug IDs/details are propagated: they may echo inputs.
                            code = ("paypal_auth_failed" if status == 401 or is_oauth else
                                    "paypal_declined" if status == 422 else "paypal_not_found" if status == 404 else
                                    "paypal_provider_unavailable" if status >= 500 or status in {408, 429} else "paypal_request_rejected")
                            raise PayPalError(code, method == "POST" and not is_oauth and (status >= 500 or status in {408, 429}))
                        try:
                            result = json.loads(body)
                            if not isinstance(result, dict):
                                raise ValueError()
                            return result
                        except (ValueError, UnicodeError, RecursionError):
                            raise PayPalError("paypal_invalid_response", method == "POST" and not is_oauth) from None
                    except httpx.TransportError:
                        if not can_retry or attempt >= self.settings.paypal_retries:
                            raise PayPalError("paypal_transport_error", method == "POST" and not is_oauth) from None
                        await anyio.sleep(.1 * (attempt + 1))
        except TimeoutError:
            raise PayPalError("paypal_timeout", method == "POST" and not is_oauth) from None
        except DestinationError:
            raise PayPalError("paypal_destination_blocked") from None
        raise PayPalError("paypal_provider_unavailable")

    async def access_token(self) -> str:
        async with self._oauth_lock:
            if not configured(self.settings):
                raise PayPalError("paypal_not_configured")
            binding = client_binding(self.settings)
            if self._token and self._token_binding == binding and monotonic() < self._expires:
                return self._token
            data = await self.request("POST", BASE + "/v1/oauth2/token",
                auth=httpx.BasicAuth(self.settings.paypal_client_id.get_secret_value(), self.settings.paypal_client_secret.get_secret_value()),
                data={"grant_type": "client_credentials"})
            token, ttl = data.get("access_token"), data.get("expires_in")
            if (not isinstance(token, str) or not token or len(token) > 8192
                    or any(ord(c) < 33 or ord(c) > 126 for c in token)
                    or data.get("token_type", "").lower() != "bearer" or type(ttl) is not int or not 0 < ttl <= 86400):
                raise PayPalError("paypal_invalid_oauth_response")
            self._token = token
            self._token_binding = binding
            self._expires = monotonic() + max(0, ttl - 60)
            return token

    async def sdk_call(self, controller: str, method: str, options: dict) -> dict:
        token = await self.access_token()
        config = Configuration(environment=Environment.SANDBOX, max_retries=0,
            client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
                "server-owned", "server-owned", o_auth_token=OAuthToken(token, "Bearer", expiry=int(time()) + 3600)))
        config.set_http_client(SdkTransport(self))
        sdk = PaypalServersdkClient(config=config)
        try:
            result = await anyio.to_thread.run_sync(lambda: getattr(getattr(sdk, controller), method)(options))
            return APIHelper.to_dictionary(result.body)
        except PayPalError as exc:
            if exc.code == "paypal_auth_failed":
                self._token = None  # The next explicit operation may authenticate; no hidden financial replay.
            raise
        except Exception:
            raise PayPalError("paypal_invalid_response", method in {"create_order", "capture_order"}) from None

    async def create_order(self, payment: dict, callback_state: str) -> dict:
        callback = self.settings.paypal_callback_base_url + "/api/payments/return/" + payment["run_id"] + "/" + payment["id"]
        body = {"intent": "CAPTURE", "purchase_units": [{"reference_id": payment["id"], "custom_id": payment["run_id"],
            "amount": {"currency_code": payment["currency"], "value": amount_value(payment["amount_minor"], payment["currency"])}}], "payment_source": {"paypal": {"experience_context": {
                "return_url": callback + "?state=" + callback_state,
                "cancel_url": callback + "?state=" + callback_state + "&cancelled=true",
                "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING"}}}}
        # Direct first-party Orders defaults to the authenticated app's merchant.
        # Never supply an email or infer an account ID from client credentials.
        if payment["merchant_id"]:
            body["purchase_units"][0]["payee"] = {"merchant_id": payment["merchant_id"]}
        return await self.sdk_call("orders", "create_order", {"body": OrderRequest.from_dictionary(body),
            "paypal_request_id": payment["create_key"], "prefer": "return=representation"})

    async def get_order(self, order_id: str) -> dict:
        self.check_id(order_id)
        return await self.sdk_call("orders", "get_order", {"id": order_id})

    async def capture_order(self, order_id: str, request_id: str) -> dict:
        self.check_id(order_id)
        return await self.sdk_call("orders", "capture_order", {"id": order_id, "paypal_request_id": request_id,
                                                               "prefer": "return=representation"})

    async def get_capture(self, capture_id: str) -> dict:
        self.check_id(capture_id)
        return await self.sdk_call("payments", "get_captured_payment", {"capture_id": capture_id})

    @staticmethod
    def check_id(value: str) -> None:
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise PayPalError("paypal_invalid_identifier")
