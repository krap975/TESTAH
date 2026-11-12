"""Export the candidate interface only, without loading Testah settings or data.

Run from the repository root with backend/.venv/Scripts/python.exe.
This is documentation tooling, not a new application or an executable tool route.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.schemas.protocol import AgentRequest, AgentResponse

DESTINATION = ROOT / "docs/developer/candidate-agent.openapi.json"

REQUEST_EXAMPLE = {
    "protocol_version": "1.0",
    "request_id": "request-demo-001",
    "session_id": "connection-test-demo-001",
    "message": {"role": "user", "content": "Please confirm protocol compatibility."},
    "history": [],
    "available_tools": [{
        "name": "test_echo",
        "description": "Protocol demonstration only; this probe never executes tools.",
        "input_schema": {
            "type": "object", "properties": {"text": {"type": "string"}},
            "required": ["text"], "additionalProperties": False,
        },
    }],
    "previous_tool_result": None,
    "context": {"purpose": "connection_test", "sample_response_mode": "message"},
}
ENVELOPE = {key: REQUEST_EXAMPLE[key] for key in ("protocol_version", "request_id", "session_id")}
MINIMAL_REQUEST_EXAMPLE = {key: REQUEST_EXAMPLE[key] for key in
                           ("protocol_version", "request_id", "session_id", "message")}
RESPONSE_EXAMPLES = {
    "message": {**ENVELOPE, "type": "message", "message": "Protocol request received."},
    "tool_call": {**ENVELOPE, "type": "tool_call", "tool_call": {
        "correlation_id": "call-demo-001", "name": "test_echo", "arguments": {"text": "Example only."},
    }},
    "completed": {**ENVELOPE, "type": "completed", "summary": "Protocol demonstration finished; no purchase was performed."},
}


def build_specification() -> dict:
    """Derive a documentation-only operation from the unchanged wire models."""
    app = FastAPI(
        title="Testah Candidate Agent Protocol",
        version="1.0",
        description=(
            "The agent developer implements this endpoint; Testah is its HTTP client. "
            "This specification contains only the candidate interface, not Testah's operational API. "
            "Return one response with matching protocol_version, request_id and session_id. "
            "A tool_call requests gateway execution; it does not execute a tool directly. "
            "A completed response is a candidate claim, not an assessment result. "
            "Strict Python validation also rejects coercion, duplicate JSON keys and non-finite numbers. "
            "The placeholder server is not a live service."
        ),
        servers=[{"url": "https://candidate.invalid", "description": "Non-resolving placeholder; replace with the approved candidate origin."}],
    )

    @app.post(
        "/agent", response_model=AgentResponse, operation_id="respondToTestah",
        summary="Respond to one Testah candidate request", tags=["Candidate agent"],
        description=(
            "Implement this POST on the external candidate service. Send HTTP 200 with uncompressed "
            "application/json. Return exactly one message, tool_call, or completed response; echo identifiers exactly. "
            "Only advertised tools may be requested. Use a fresh tool correlation_id for each call within a run. "
            "Testah sends the gateway result in previous_tool_result on a subsequent exchange. "
            "Requests are limited to 65536 serialized UTF-8 bytes; responses default to 65536 bytes. "
            "The total exchange deadline defaults to 10 seconds (operator-configurable from 1 to 60). "
            "Testah never automatically retries this POST. Redirects and compressed responses are rejected. "
            "Authentication and validation errors documented here describe the standalone FastAPI sample; "
            "Testah maps non-success HTTP responses to its own safe connector errors."
        ),
    )
    def candidate(request: Annotated[AgentRequest, Body(openapi_examples={
        "compatibility": {"summary": "Minimal synthetic compatibility request; optional fields may be omitted", "value": MINIMAL_REQUEST_EXAMPLE},
    })]) -> AgentResponse:
        raise RuntimeError("Documentation-only declaration; never serve this application.")

    spec = app.openapi()
    operation = spec["paths"]["/agent"]["post"]
    operation["responses"]["200"]["content"]["application/json"]["examples"] = {
        name: {"summary": name.replace("_", " "), "value": value}
        for name, value in RESPONSE_EXAMPLES.items()
    }
    spec["components"]["securitySchemes"] = {
        "CandidateAuthorization": {
            "type": "apiKey", "in": "header", "name": "Authorization",
            "description": "Optional complete header value configured server-side by the operator. No automatic Bearer prefix is added. Never publish a real value.",
        },
    }
    operation["security"] = [{"CandidateAuthorization": []}, {}]
    operation["responses"]["401"] = {
        "description": "The sample rejects missing or incorrect authentication when its optional token is configured.",
        "content": {"application/json": {"schema": {
            "type": "object", "properties": {"detail": {"type": "string"}}, "required": ["detail"],
        }, "example": {"detail": "Authentication required."}}},
    }
    # APIMatic requires named polymorphic responses and unique schema titles.
    # Lift the union unchanged and remove Pydantic's cosmetic repeated titles.
    # Required fields, constraints, consts, oneOf and discriminator stay intact.
    schemas = spec["components"]["schemas"]
    # New FastAPI versions document optional input/ctx on validation errors.
    # Keep the published open error object stable; extra properties remain allowed.
    for optional_detail in ("input", "ctx"):
        schemas["ValidationError"]["properties"].pop(optional_detail, None)
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    schemas["AgentResponse"] = response_schema
    operation["responses"]["200"]["content"]["application/json"]["schema"] = {"$ref": "#/components/schemas/AgentResponse"}

    def remove_titles(value):
        if isinstance(value, dict):
            value.pop("title", None)
            for child in value.values():
                remove_titles(child)
        elif isinstance(value, list):
            for child in value:
                remove_titles(child)

    remove_titles(schemas)
    # Pydantic emits JsonValue as {}. The v1 documentation generator otherwise
    # replaces scalar examples in maps with synthetic objects. Enumerating all
    # JSON types is equivalent over JSON and lets it retain those example types.
    schemas["JsonValue"] = {"anyOf": [{"type": kind} for kind in
                           ("string", "number", "boolean", "null", "array", "object")]}
    descriptions = {
        "AgentRequest": "One bounded version 1.0 exchange sent by Testah to the candidate.",
        "AgentResponse": "Exactly one response variant, selected by type; identifiers must match the request.",
        "MessageResponse": "A conversational reply, without a tool request or completion claim.",
        "ToolCallResponse": "One request for a permitted tool; execution remains with Testah's gateway.",
        "CompletedResponse": "A candidate completion claim, independently verified by the controller.",
        "CustomerMessage": "The current customer message supplied by Testah.",
        "Message": "An ordered public history message; tool content contains serialized JSON.",
        "ToolDefinition": "An advertised name, description and argument schema; not execution authority.",
        "ToolCall": "A fresh run-scoped correlation, advertised tool name and argument object.",
        "ToolResult": "A correlated gateway success or safe error, supplied on a subsequent exchange.",
        "JsonValue": "Any finite JSON value, including nested objects, arrays and null.",
        "HTTPValidationError": "Standalone FastAPI sample validation failure; not Testah's management error envelope.",
        "ValidationError": "A sample validation detail; never put sensitive values in a protocol request.",
    }
    for name, schema in schemas.items():
        schema["description"] = descriptions[name]
    schemas["AgentRequest"]["example"] = MINIMAL_REQUEST_EXAMPLE
    for name, kind in (("MessageResponse", "message"), ("ToolCallResponse", "tool_call"), ("CompletedResponse", "completed")):
        schemas[name]["example"] = RESPONSE_EXAMPLES[kind]
    spec["info"]["contact"] = {"name": "Testah project operator"}
    operation["requestBody"]["description"] = "Strict candidate request. All examples are synthetic; the probe executes no tools."
    spec["x-testah-contract-source"] = "backend/app/schemas/protocol.py"
    spec["x-testah-transport"] = {
        "request_max_bytes": 65536, "response_default_max_bytes": 65536,
        "default_total_timeout_seconds": 10, "automatic_post_retries": 0,
    }
    return spec


def rendered_specification() -> str:
    return json.dumps(build_specification(), indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in contract differs; write nothing.")
    args = parser.parse_args()
    rendered = rendered_specification()
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Candidate contract is stale. Run this exporter without --check.")
        print("PASS candidate-only OpenAPI matches the executable wire schemas")
    else:
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_text(rendered, encoding="utf-8")
        print("Exported docs/developer/candidate-agent.openapi.json (POST /agent only)")


if __name__ == "__main__":
    main()
