import pytest
from pydantic import ValidationError
from app.schemas.protocol import ToolCall, ToolDefinition
from app.tools.registry import tool_definitions, tool_names, validate_tool_call

VALID = {
    "search_products": {"query":"headphones","max_price_minor":10000},
    "get_merchant_details": {"merchant_id":"syn-merchant-primary"},
    "get_budget": {},
    "request_approval": {"merchant_id":"syn-merchant-primary","items":[{"product_id":"syn-product-premium","quantity":1}],"total_minor":9500,"currency":"USD","cart_version":1},
    "create_checkout": {"approval_id":"approval-1","idempotency_key":"checkout-1","cart_version":1},
    "get_payment_status": {"checkout_id":"checkout-1"},
}

def test_definitions_reuse_phase_two_structure_without_shared_mutable_state():
    definitions = tool_definitions()
    assert {item.name for item in definitions} == set(VALID)
    assert all(type(item) is ToolDefinition for item in definitions)
    assert all(item.input_schema["additionalProperties"] is False for item in definitions)
    definitions[0].input_schema.clear()
    assert tool_definitions()[0].input_schema

@pytest.mark.parametrize("name",list(VALID))
def test_tool_argument_validation_only(name):
    request = ToolCall(correlation_id="call-1",name=name,arguments=VALID[name])
    result = validate_tool_call(request,list(VALID))
    assert result.model_dump(exclude_unset=True) == VALID[name]
    with pytest.raises(ValidationError):
        validate_tool_call(ToolCall(correlation_id="call-1",name=name,arguments={**VALID[name],"unexpected":True}),list(VALID))

@pytest.mark.parametrize("name,args", [
    ("search_products",{"max_price_minor":1.5}), ("get_merchant_details",{}),
    ("get_budget",{"session_id":"untrusted"}),
    ("request_approval",{**VALID["request_approval"],"total_minor":True}),
    ("request_approval",{**VALID["request_approval"],"currency":"ZZZ"}),
    ("request_approval",{**VALID["request_approval"],"items":[]}),
    ("request_approval",{**VALID["request_approval"],"items":[{"product_id":"same","quantity":1},{"product_id":"same","quantity":1}]}),
    ("create_checkout",{"approval_id":"a","idempotency_key":"b","cart_version":0}),
    ("get_payment_status",{})
])
def test_unsafe_argument_shapes_are_rejected(name,args):
    with pytest.raises(ValidationError): validate_tool_call(ToolCall(correlation_id="c",name=name,arguments=args),list(VALID))

def test_unknown_and_disallowed_tools():
    with pytest.raises(ValueError): validate_tool_call(ToolCall(correlation_id="c",name="run_shell",arguments={}),["run_shell"])
    with pytest.raises(ValueError): validate_tool_call(ToolCall(correlation_id="c",name="get_budget",arguments={}),[])

