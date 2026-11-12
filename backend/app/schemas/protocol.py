"""Framework-independent candidate protocol. No execution or scoring semantics."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
Text = Annotated[str, Field(min_length=1, max_length=16000)]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

class Message(StrictModel):
    role: Literal["user", "assistant", "tool"]
    content: Text

class CustomerMessage(StrictModel):
    role: Literal["user"] = "user"
    content: Text

class ToolDefinition(StrictModel):
    name: Identifier
    description: Annotated[str, Field(min_length=1, max_length=2000)]
    input_schema: dict[str, JsonValue]

class ToolResult(StrictModel):
    correlation_id: Identifier
    name: Identifier
    status: Literal["success", "error"]
    result: dict[str, JsonValue]

class AgentRequest(StrictModel):
    protocol_version: Literal["1.0"]
    request_id: Identifier
    session_id: Identifier
    message: CustomerMessage
    history: Annotated[list[Message], Field(max_length=100)] = Field(default_factory=list)
    available_tools: Annotated[list[ToolDefinition], Field(max_length=50)] = Field(default_factory=list)
    previous_tool_result: ToolResult | None = None
    context: dict[str, JsonValue] = Field(default_factory=dict)

class ResponseEnvelope(StrictModel):
    protocol_version: Literal["1.0"]
    request_id: Identifier
    session_id: Identifier

class MessageResponse(ResponseEnvelope):
    type: Literal["message"]
    message: Text

class ToolCall(StrictModel):
    correlation_id: Identifier
    name: Identifier
    arguments: dict[str, JsonValue]

class ToolCallResponse(ResponseEnvelope):
    type: Literal["tool_call"]
    tool_call: ToolCall

class CompletedResponse(ResponseEnvelope):
    type: Literal["completed"]
    summary: Text

AgentResponse = Annotated[MessageResponse | ToolCallResponse | CompletedResponse, Field(discriminator="type")]
response_adapter = TypeAdapter(AgentResponse)

