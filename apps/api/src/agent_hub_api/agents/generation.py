from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ModelToolDefinition:
    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True, slots=True)
class ModelUserMessage:
    content: str


@dataclass(frozen=True, slots=True)
class ModelAssistantMessage:
    content: str | None
    tool_calls: tuple[ModelToolCall, ...]


@dataclass(frozen=True, slots=True)
class ModelToolResultMessage:
    tool_call_id: str
    content: str


ModelMessage = ModelUserMessage | ModelAssistantMessage | ModelToolResultMessage


@dataclass(frozen=True, slots=True)
class ModelRequest:
    system_prompt: str
    messages: tuple[ModelMessage, ...]
    tools: tuple[ModelToolDefinition, ...]
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str | None
    tool_calls: tuple[ModelToolCall, ...]
    usage: ModelUsage


class ModelGateway(Protocol):
    async def generate(self, request: ModelRequest) -> ModelResponse: ...


class ModelTemporaryError(RuntimeError):
    """The model provider is temporarily unavailable."""


class ModelPermanentError(RuntimeError):
    """The provider rejected model configuration or bounded input."""
