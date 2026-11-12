"""Additive design input; never a replacement for the authoritative v1 Blueprint."""
import re
from typing import Annotated, Literal
from pydantic import Field, field_validator
from app.schemas.environments import Persona, ShortText
from app.schemas.protocol import Identifier, StrictModel
from app.tools.registry import Currency, PositiveMinor

TemplateId = Literal["budget_constrained_purchase", "merchant_trust_verification", "price_change_before_checkout"]


def safe_scenario_text(value: str) -> str:
    # Deliberately conservative: descriptive copy must not impersonate instructions
    # or claim authorization. Financial authority never derives from this filter.
    if any(ord(c) < 32 for c in value) or re.search(
        r"(?i)https?://|\b(ignore|override|bypass|system|developer|secret|password|credential|token|api.key|approved|authorized|granted|paypal)\b", value
    ):
        raise ValueError("Scenario copy contains unsupported instructions or sensitive content.")
    return value


class ProductVariation(StrictModel):
    product_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=200)]
    price_minor: PositiveMinor


class MerchantVariation(StrictModel):
    merchant_id: Identifier
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    shipping_fee_minor: Annotated[int, Field(ge=0, le=1_000_000_000)]


class ChallengeSelection(StrictModel):
    challenge_id: Identifier
    increase_minor: PositiveMinor | None


class EnvironmentDesign(StrictModel):
    version: Literal["1.0"]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    template_id: TemplateId
    template_version: Literal["1.0"]
    category: Literal["headphones"]
    customer: Persona
    objective: ShortText
    currency: Currency
    budget_minor: Annotated[int, Field(ge=1000, le=1_000_000)]
    products: Annotated[list[ProductVariation], Field(max_length=5)]
    merchants: Annotated[list[MerchantVariation], Field(max_length=4)]
    challenges: Annotated[list[ChallengeSelection], Field(max_length=2)]

    @field_validator("name", "objective")
    @classmethod
    def safe_copy(cls, value: str) -> str:
        return safe_scenario_text(value)
