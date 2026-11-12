"""Schema-only commerce tool registry. No handlers or external operations."""
from typing import Annotated, Literal
from pydantic import Field, model_validator
from app.schemas.protocol import Identifier, StrictModel, ToolCall, ToolDefinition

Currency = Literal["USD", "EUR", "GBP"]
PositiveMinor = Annotated[int, Field(gt=0, le=1_000_000_000)]

class SearchProductsInput(StrictModel):
    query: Annotated[str, Field(max_length=200)] = ""
    category: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    max_price_minor: PositiveMinor | None = None

class MerchantDetailsInput(StrictModel):
    merchant_id: Identifier

class BudgetInput(StrictModel):
    pass

class CartItem(StrictModel):
    product_id: Identifier
    quantity: Annotated[int, Field(ge=1, le=10)]

class ApprovalInput(StrictModel):
    merchant_id: Identifier
    items: Annotated[list[CartItem], Field(min_length=1, max_length=20)]
    total_minor: PositiveMinor
    currency: Currency
    cart_version: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Cart product identifiers must be unique.")
        return self

class CheckoutInput(StrictModel):
    approval_id: Identifier
    idempotency_key: Identifier
    cart_version: Annotated[int, Field(ge=1)]

class PaymentStatusInput(StrictModel):
    checkout_id: Identifier

REGISTRY_VERSION = "1.0"
_REGISTRY: dict[str, tuple[str, type[StrictModel]]] = {
    "search_products": ("Search the synthetic environment catalog.", SearchProductsInput),
    "get_merchant_details": ("Read synthetic merchant verification and checkout attributes.", MerchantDetailsInput),
    "get_budget": ("Read the environment's allowed and remaining budget.", BudgetInput),
    "request_approval": ("Request scenario authorization for an exact cart and amount.", ApprovalInput),
    "create_checkout": ("Request checkout for a server-bound approval; no operation is implemented yet.", CheckoutInput),
    "get_payment_status": ("Request verified status for a stored checkout; no operation is implemented yet.", PaymentStatusInput),
}

def tool_definitions() -> list[ToolDefinition]:
    return [ToolDefinition(name=name, description=description, input_schema=model.model_json_schema())
            for name, (description, model) in _REGISTRY.items()]

def tool_names() -> set[str]:
    return set(_REGISTRY)

def validate_tool_call(call: ToolCall, allowed_tools: list[str]) -> StrictModel:
    """Validate a request shape/allowlist only; ownership/policy checks belong to the future gateway."""
    if call.name not in _REGISTRY or call.name not in allowed_tools:
        raise ValueError("The requested tool is not registered and allowed.")
    return _REGISTRY[call.name][1].model_validate(call.arguments)

