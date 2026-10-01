from __future__ import annotations

from collections.abc import Mapping

import openai
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
)
from openai.types.shared_params import FunctionDefinition

from agent_hub_api.agents.generation import (
    ModelGateway,
    ModelMessage,
    ModelPermanentError,
    ModelRequest,
    ModelResponse,
    ModelTemporaryError,
    ModelToolCall,
    ModelToolDefinition,
    ModelToolResultMessage,
    ModelUsage,
    ModelUserMessage,
)
from agent_hub_api.core.config import Settings


def _error_code(exc: openai.APIStatusError) -> str | None:
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        return code
    body = getattr(exc, "body", None)
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping):
            nested = error.get("code")
            if isinstance(nested, str):
                return nested
    return None


class OpenAIGenerationGateway(ModelGateway):
    """Non-streaming OpenAI tool-call adapter for the bounded F3.4 runtime."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        client: AsyncOpenAI | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("A verified OpenAI generation model is required")
        if client is None and not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI generation")
        self.model = model.strip()
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        params = CompletionCreateParamsNonStreaming(
            model=self.model,
            messages=self._messages(request),
            tools=[self._tool(tool) for tool in request.tools],
            tool_choice="required",
            parallel_tool_calls=False,
            max_completion_tokens=request.max_output_tokens,
            store=False,
        )
        if self.model == "gpt-6-luna":
            # GPT-6 Luna supports Chat Completions function calling only when
            # reasoning is disabled. Other configured models retain their native
            # defaults rather than receiving a model-specific parameter.
            params["reasoning_effort"] = "none"
        try:
            response = await self._client.chat.completions.create(**params)
        except openai.RateLimitError as exc:
            if _error_code(exc) == "credit_balance_exhausted":
                raise ModelPermanentError("OpenAI credit balance is exhausted") from exc
            raise ModelTemporaryError("OpenAI generation rate limit reached") from exc
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.APIResponseValidationError,
        ) as exc:
            raise ModelTemporaryError(
                "OpenAI generation is temporarily unavailable"
            ) from exc
        except (
            openai.AuthenticationError,
            openai.BadRequestError,
            openai.NotFoundError,
            openai.PermissionDeniedError,
            openai.UnprocessableEntityError,
        ) as exc:
            raise ModelPermanentError("OpenAI rejected the generation request") from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ModelTemporaryError(
                    "OpenAI generation is temporarily unavailable"
                ) from exc
            raise ModelPermanentError("OpenAI rejected the generation request") from exc
        except openai.OpenAIError as exc:
            raise ModelPermanentError("OpenAI generation failed") from exc

        if len(response.choices) != 1 or response.usage is None:
            raise ModelTemporaryError("OpenAI returned an incomplete generation response")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ModelPermanentError("OpenAI generation reached its output limit")
        message = choice.message
        if message.refusal:
            raise ModelPermanentError("OpenAI refused the generation request")
        tool_calls = tuple(
            ModelToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments_json=tool_call.function.arguments,
            )
            for tool_call in message.tool_calls or ()
            if tool_call.type == "function"
        )
        return ModelResponse(
            content=message.content,
            tool_calls=tool_calls,
            usage=ModelUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
        )

    async def close(self) -> None:
        await self._client.close()

    @staticmethod
    def _messages(request: ModelRequest) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": request.system_prompt}
        ]
        for message in request.messages:
            messages.append(OpenAIGenerationGateway._message(message))
        return messages

    @staticmethod
    def _message(message: ModelMessage) -> ChatCompletionMessageParam:
        if isinstance(message, ModelUserMessage):
            return {"role": "user", "content": message.content}
        if isinstance(message, ModelToolResultMessage):
            return ChatCompletionToolMessageParam(
                role="tool",
                tool_call_id=message.tool_call_id,
                content=message.content,
            )
        tool_calls = [
            ChatCompletionMessageFunctionToolCallParam(
                id=tool_call.id,
                type="function",
                function={
                    "name": tool_call.name,
                    "arguments": tool_call.arguments_json,
                },
            )
            for tool_call in message.tool_calls
        ]
        return ChatCompletionAssistantMessageParam(
            role="assistant",
            content=message.content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _tool(tool: ModelToolDefinition) -> ChatCompletionToolParam:
        return ChatCompletionToolParam(
            type="function",
            function=FunctionDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                # Pydantic validates every call locally. Some approved model families do
                # not support OpenAI's stricter all-fields-required JSON-schema subset.
                strict=False,
            ),
        )


def create_openai_generation_gateway(settings: Settings) -> OpenAIGenerationGateway:
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is required for OpenAI generation")
    if settings.generation_model is None:
        raise ValueError("GENERATION_MODEL must name an explicitly verified model")
    return OpenAIGenerationGateway(
        model=settings.generation_model,
        api_key=settings.openai_api_key,
        timeout_seconds=settings.openai_timeout_seconds,
    )
