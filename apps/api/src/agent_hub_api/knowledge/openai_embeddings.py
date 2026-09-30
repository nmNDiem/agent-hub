from __future__ import annotations

from collections.abc import Mapping

import openai
from openai import AsyncOpenAI

from agent_hub_api.knowledge.providers import (
    EmbeddingProfileSpec,
    ProviderPermanentError,
    ProviderTemporaryError,
)


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


class OpenAIEmbeddingProvider:
    """OpenAI embedding adapter with retries delegated to the durable worker."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        client: AsyncOpenAI | None = None,
    ) -> None:
        if client is None and not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI embedding provider")
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def embed(
        self, profile: EmbeddingProfileSpec, texts: list[str]
    ) -> list[tuple[float, ...]]:
        if profile.provider != "openai":
            raise ProviderPermanentError("Embedding profile provider is not OpenAI")
        if not texts or any(not text for text in texts):
            raise ProviderPermanentError("Embedding input must contain non-empty text")
        try:
            response = await self._client.embeddings.create(
                model=profile.model,
                input=texts,
                dimensions=profile.dimensions,
                encoding_format="float",
            )
        except openai.RateLimitError as exc:
            if _error_code(exc) == "credit_balance_exhausted":
                raise ProviderPermanentError("OpenAI credit balance is exhausted") from exc
            raise ProviderTemporaryError("OpenAI rate limit reached") from exc
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.APIResponseValidationError,
        ) as exc:
            raise ProviderTemporaryError(
                "OpenAI embedding request is temporarily unavailable"
            ) from exc
        except (
            openai.AuthenticationError,
            openai.BadRequestError,
            openai.NotFoundError,
            openai.PermissionDeniedError,
            openai.UnprocessableEntityError,
        ) as exc:
            raise ProviderPermanentError("OpenAI rejected the embedding configuration") from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderTemporaryError(
                    "OpenAI embedding request is temporarily unavailable"
                ) from exc
            raise ProviderPermanentError("OpenAI rejected the embedding request") from exc
        except openai.OpenAIError as exc:
            raise ProviderPermanentError("OpenAI embedding request failed") from exc

        rows = sorted(response.data, key=lambda item: item.index)
        if len(rows) != len(texts):
            raise ProviderTemporaryError("OpenAI returned an incomplete embedding batch")
        vectors = [tuple(float(value) for value in row.embedding) for row in rows]
        if any(len(vector) != profile.dimensions for vector in vectors):
            raise ProviderPermanentError("OpenAI returned an unexpected embedding dimension")
        return vectors
