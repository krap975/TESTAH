"""Fixed public guidance. Never interpolate provider bodies or exception messages."""

MESSAGES = {
    "provider_network_denied": "The backend process was denied outbound network access. Start the API in an authorized network-enabled terminal and run the provider check. Increasing timeouts will not fix permission denial.",
    "provider_dns_error": "The backend could not resolve the provider hostname. Check DNS access in the API runtime.",
    "provider_destination_blocked": "Provider DNS returned a destination rejected by the public-network policy. Check DNS configuration; do not disable destination validation.",
    "provider_tls_error": "The backend could not establish verified TLS. Check the runtime's certificate trust and network inspection configuration; keep certificate verification enabled.",
    "provider_proxy_error": "The provider transport reported a proxy failure. Testah uses direct HTTPS and does not inherit environment proxies. Check the API runtime's network policy.",
    "provider_unreachable": "The backend could not connect to the provider. Run the provider check in this API process and check outbound HTTPS access.",
    "provider_timeout": "The provider operation exceeded its bounded timeout. Check backend timing logs and run the provider check before retrying.",
    "provider_not_configured": "The provider model or server-side API key is missing or invalid. Check backend/.env and restart the API.",
    "provider_authentication_failed": "The provider rejected API access. Check the server-side key, API restrictions and account permissions.",
    "provider_model_unavailable": "The configured model was not found. Check model access for the API account.",
    "provider_transient_error": "The provider returned rate limiting or a server failure after bounded retries. Check quota and provider availability before retrying.",
    "provider_http_error": "The provider rejected the request. Check the sanitized HTTP status in backend logs and verify model, key restrictions and request configuration.",
    "provider_protocol_error": "The provider connection returned an invalid HTTP response. Check the API runtime's network path.",
    "provider_transport_error": "The provider transport failed. Check sanitized backend logs and runtime connectivity.",
    "provider_incomplete": "The provider did not finish a complete response within its output constraints. Retry the proposal or review the bounded output configuration.",
    "provider_refusal": "The provider refused the generation. Review the agent's capability description before retrying.",
    "invalid_model_output": "The provider response was not valid structured JSON. Bounded repair did not produce an acceptable proposal.",
    "invalid_environment_proposal": "The generated design failed deterministic environment validation. Review the inputs and retry.",
    "generation_timeout": "The proposal reached its total generation deadline. Review provider timings before retrying.",
    "generation_worker_stopped": "The API stopped during generation. Start a new proposal after the backend is ready.",
    "generation_worker_expired": "The generation worker lease expired. Check the backend process and submit a new proposal.",
}


def failure_message(code: str) -> str:
    return MESSAGES.get(code, "The operation failed safely. Check sanitized backend logs and retry when the cause is resolved.")
