from urllib.parse import urlsplit

from agent_hub_api.channels.contracts import (
    ChannelCapabilities,
    ChannelProvider,
    NormalizedOutboundMessage,
    RenderedOutboundMessage,
)


class ChannelRenderError(ValueError):
    pass


class CapabilityAwareRenderer:
    def __init__(
        self,
        *,
        provider: ChannelProvider,
        capabilities: ChannelCapabilities,
        max_text_characters: int,
    ) -> None:
        if max_text_characters < 1:
            raise ValueError("Channel text limit must be positive")
        self.provider = provider
        self.capabilities = capabilities
        self.max_text_characters = max_text_characters

    def render(self, message: NormalizedOutboundMessage) -> RenderedOutboundMessage:
        if not self.capabilities.text:
            raise ChannelRenderError("CHANNEL_TEXT_UNSUPPORTED")
        for link in message.product_links:
            parsed = urlsplit(link)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ChannelRenderError("INVALID_PRODUCT_LINK")

        fallback_parts: list[str] = []
        product_links = message.product_links
        source_labels = message.source_labels
        if message.product_links and not self.capabilities.product_cards:
            fallback_parts.append("\n".join(f"- {link}" for link in message.product_links))
            product_links = ()
        if message.source_labels and not self.capabilities.source_references:
            fallback_parts.append("Nguồn: " + "; ".join(message.source_labels))
            source_labels = ()
        rendered_text = "\n\n".join((message.text, *fallback_parts))
        if len(rendered_text) > self.max_text_characters:
            raise ChannelRenderError("CHANNEL_TEXT_LIMIT_EXCEEDED")
        return RenderedOutboundMessage(
            text=rendered_text,
            fallback_used=bool(fallback_parts),
            product_links=product_links,
            source_labels=source_labels,
        )
