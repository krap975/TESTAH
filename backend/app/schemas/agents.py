from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.execution.network import LOCAL_SAMPLE_URL, validate_external_url

Name = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=4000)]
Mode = Literal["external", "local_sample"]

class Authentication(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    header_name: Literal["Authorization", "X-API-Key"]
    secret_key: Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]

class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    name: Name
    description: Description = ""
    endpoint_url: Annotated[str, Field(min_length=1, max_length=2048)]
    connection_mode: Mode = "external"
    authentication: Authentication | None = None

    @model_validator(mode="after")
    def endpoint_policy(self):
        if self.connection_mode == "local_sample":
            if self.endpoint_url != LOCAL_SAMPLE_URL:
                raise ValueError("The local sample uses its fixed development endpoint.")
        else:
            self.endpoint_url = validate_external_url(self.endpoint_url)
        return self

class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    name: Name | None = None
    description: Description | None = None
    endpoint_url: Annotated[str, Field(min_length=1, max_length=2048)] | None = None
    connection_mode: Mode | None = None
    authentication: Authentication | None = None

    @model_validator(mode="after")
    def reject_null_metadata(self):
        for key in ("name", "description", "endpoint_url", "connection_mode"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError("Metadata fields cannot be null.")
        return self

class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    endpoint_url: str
    connection_mode: Mode
    authentication_configured: bool
    auth_header_name: str | None
    created_at: datetime
    updated_at: datetime
    last_test_status: Literal["not_tested", "connected", "failed"]
    last_test_at: datetime | None
    last_test_code: str | None
    last_test_message: str | None

    @field_validator("created_at", "updated_at", "last_test_at", mode="after")
    @classmethod
    def utc_timestamps(cls, value):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value

class ConnectionTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    response_mode: Literal["message", "tool_call", "completed"] = "message"

class ConnectionTestResult(BaseModel):
    status: Literal["connected"] = "connected"
    request_id: str
    response_type: Literal["message", "tool_call", "completed"]
    message: str = "A valid protocol response was received. No tools were executed."

