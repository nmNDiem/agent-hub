import {
  WidgetApiError,
  createConversation,
  createSession,
  deleteConversation,
  deleteImage,
  fetchProductImage,
  getTranscript,
  streamMessage,
  uploadImage,
  validStoredSession,
} from "./api";
import { widgetStyles } from "./styles";
import type {
  PublicProductCard,
  PublicSource,
  TranscriptItem,
  WidgetConfig,
  WidgetMessage,
} from "./types";

type StoredSession = {
  token: string;
  expiresAt: string;
  conversationId: string;
  config: WidgetConfig;
};

type PendingAttachment = {
  attachmentId?: string;
  fileName: string;
  previewUrl: string;
  uploading: boolean;
};

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function priceLabel(card: PublicProductCard): string {
  if (card.price.kind === "unknown" || card.price.minimum === null) return "Chưa có giá xác minh";
  const format = (raw: string) => {
    const value = Number(raw);
    if (!Number.isFinite(value)) return raw;
    return new Intl.NumberFormat("vi-VN", {
      style: "currency",
      currency: card.currency,
      maximumFractionDigits: 2,
    }).format(value);
  };
  if (card.price.kind === "range" && card.price.maximum !== null) {
    return `${format(card.price.minimum)} – ${format(card.price.maximum)}`;
  }
  return format(card.price.minimum);
}

function stockLabel(card: PublicProductCard): { text: string; available: boolean } {
  if (card.availability.in_stock_locations > 0) {
    return {
      text: `Còn hàng tại ${card.availability.in_stock_locations} nơi`,
      available: true,
    };
  }
  if (card.availability.unknown_locations > 0 || card.availability.total_locations === 0) {
    return { text: "Tồn kho chưa xác định", available: false };
  }
  return { text: "Hiện đang hết hàng", available: false };
}

function transcriptMessage(item: TranscriptItem): WidgetMessage {
  return {
    id: item.response_id ?? crypto.randomUUID(),
    role: item.role,
    text: item.text,
    state: item.status === "completed" ? "complete" : "cancelled",
    products: item.product_cards,
    sources: item.sources,
  };
}

export class AgentHubWidget {
  private readonly shadow: ShadowRoot;
  private readonly storageKey: string;
  private session?: StoredSession;
  private config?: WidgetConfig;
  private messages: WidgetMessage[] = [];
  private pendingAttachment?: PendingAttachment;
  private activeController?: AbortController;
  private initialized = false;
  private initialization?: Promise<void>;
  private open = false;
  private imageUrls = new Map<string, string>();
  private objectUrls = new Set<string>();
  private readonly handleResize = () => {
    this.protectHost(this.host.dataset.position === "left" ? "left" : "right");
  };

  private readonly panel: HTMLElement;
  private readonly launcher: HTMLButtonElement;
  private readonly title: HTMLElement;
  private readonly transcript: HTMLElement;
  private readonly suggestions: HTMLElement;
  private readonly composer: HTMLFormElement;
  private readonly textarea: HTMLTextAreaElement;
  private readonly uploadButton: HTMLButtonElement;
  private readonly fileInput: HTMLInputElement;
  private readonly attachment: HTMLElement;
  private readonly error: HTMLElement;

  constructor(
    private readonly host: HTMLElement,
    private readonly agentId: string,
    private readonly apiBase: string,
  ) {
    this.storageKey = `agenthub:widget:${new URL(apiBase).origin}:${agentId}`;
    this.protectHost("right");
    this.shadow = host.attachShadow({ mode: "open" });
    const style = element("style");
    style.textContent = widgetStyles;
    this.shadow.append(style);

    this.panel = element("section", "ah-panel");
    this.panel.hidden = true;
    this.panel.setAttribute("role", "dialog");
    this.panel.setAttribute("aria-label", "Trò chuyện với trợ lý cửa hàng");
    this.panel.setAttribute("aria-modal", "false");

    const header = element("header", "ah-header");
    const avatar = element("span", "ah-avatar", "✦");
    avatar.setAttribute("aria-hidden", "true");
    const headerCopy = element("div", "ah-header-copy");
    this.title = element("strong", undefined, "Trợ lý cửa hàng");
    headerCopy.append(this.title, element("span", undefined, "Trợ lý mua sắm"));
    const headerActions = element("div", "ah-header-actions");
    const reset = element("button", "ah-icon-button", "↻");
    reset.type = "button";
    reset.title = "Xóa và bắt đầu cuộc trò chuyện mới";
    reset.setAttribute("aria-label", reset.title);
    reset.addEventListener("click", () => void this.resetConversation());
    const close = element("button", "ah-icon-button", "×");
    close.type = "button";
    close.title = "Đóng cửa sổ trò chuyện";
    close.setAttribute("aria-label", close.title);
    close.addEventListener("click", () => this.setOpen(false));
    headerActions.append(reset, close);
    header.append(avatar, headerCopy, headerActions);

    this.transcript = element("div", "ah-transcript");
    this.transcript.setAttribute("role", "log");
    this.transcript.setAttribute("aria-live", "polite");
    this.transcript.setAttribute("aria-busy", "true");

    this.suggestions = element("div", "ah-suggestions");
    for (const suggestion of [
      "Gợi ý sản phẩm phù hợp",
      "Tư vấn kích thước",
      "Chính sách đổi trả",
    ]) {
      const button = element("button", undefined, suggestion);
      button.type = "button";
      button.addEventListener("click", () => {
        this.textarea.value = suggestion;
        this.textarea.focus();
        this.updateComposerState();
      });
      this.suggestions.append(button);
    }

    this.attachment = element("div", "ah-attachment");
    this.attachment.hidden = true;

    this.composer = element("form", "ah-composer");
    this.error = element("p", "ah-error");
    this.error.hidden = true;
    this.error.setAttribute("role", "alert");
    const row = element("div", "ah-composer-row");
    this.uploadButton = element("button", "ah-upload", "+");
    this.uploadButton.type = "button";
    this.uploadButton.title = "Đính kèm ảnh sản phẩm";
    this.uploadButton.setAttribute("aria-label", this.uploadButton.title);
    this.uploadButton.hidden = true;
    this.uploadButton.addEventListener("click", () => this.fileInput.click());
    this.fileInput = element("input", "ah-sr-only");
    this.fileInput.type = "file";
    this.fileInput.accept = "image/jpeg,image/png,image/webp";
    this.fileInput.addEventListener("change", () => void this.selectImage());
    this.textarea = element("textarea");
    this.textarea.rows = 1;
    this.textarea.maxLength = 4000;
    this.textarea.placeholder = "Nhập tin nhắn…";
    this.textarea.setAttribute("aria-label", "Tin nhắn");
    this.textarea.addEventListener("input", () => this.updateComposerState());
    this.textarea.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (!this.activeController) void this.send();
      }
    });
    const send = element("button", "ah-send", "➤");
    send.type = "submit";
    send.title = "Gửi tin nhắn";
    send.setAttribute("aria-label", send.title);
    send.disabled = true;
    const stop = element("button", "ah-send ah-stop", "Dừng");
    stop.type = "button";
    stop.setAttribute("aria-label", "Dừng tạo câu trả lời");
    stop.addEventListener("click", () => this.activeController?.abort());
    row.append(this.uploadButton, this.fileInput, this.textarea, send, stop);
    this.composer.append(this.error, this.attachment, row, element("p", "ah-note", "Thông tin sản phẩm được kiểm tra từ dữ liệu cửa hàng"));
    this.composer.addEventListener("submit", (event) => {
      event.preventDefault();
      void this.send();
    });

    this.panel.append(header, this.transcript, this.suggestions, this.composer);
    this.launcher = element("button", "ah-launcher");
    this.launcher.type = "button";
    this.launcher.setAttribute("aria-label", "Mở trợ lý mua sắm");
    this.launcher.setAttribute("aria-expanded", "false");
    const mark = element("span", "ah-launcher-mark");
    mark.setAttribute("aria-hidden", "true");
    this.launcher.append(mark);
    this.launcher.addEventListener("click", () => this.setOpen(!this.open));
    this.shadow.append(this.panel, this.launcher);
    window.addEventListener("resize", this.handleResize, { passive: true });
    this.shadow.addEventListener("keydown", (event) => {
      if (event instanceof KeyboardEvent && event.key === "Escape" && this.open) {
        this.setOpen(false);
      }
    });
    this.renderLoading();
    this.initialization = this.initialize();
  }

  destroy(): void {
    this.activeController?.abort();
    window.removeEventListener("resize", this.handleResize);
    for (const url of this.objectUrls) URL.revokeObjectURL(url);
    this.objectUrls.clear();
    this.host.remove();
  }

  private readStoredSession(): StoredSession | undefined {
    try {
      const raw = sessionStorage.getItem(this.storageKey);
      if (!raw) return undefined;
      const parsed: unknown = JSON.parse(raw);
      return validStoredSession(parsed) ? parsed : undefined;
    } catch {
      return undefined;
    }
  }

  private persistSession(): void {
    if (!this.session) return;
    try {
      sessionStorage.setItem(this.storageKey, JSON.stringify(this.session));
    } catch {
      // The in-memory session remains usable when browser storage is unavailable.
    }
  }

  private clearStoredSession(): void {
    this.session = undefined;
    try {
      sessionStorage.removeItem(this.storageKey);
    } catch {
      // There is nothing else to clear when browser storage is unavailable.
    }
  }

  private async initialize(forceNew = false): Promise<void> {
    this.initialized = false;
    this.transcript.setAttribute("aria-busy", "true");
    this.renderLoading();
    try {
      const stored = forceNew ? undefined : this.readStoredSession();
      if (stored) {
        this.session = stored;
        this.config = stored.config;
        this.applyConfig(stored.config);
        try {
          const transcript = await getTranscript(
            this.apiBase,
            stored.token,
            stored.conversationId,
          );
          this.messages = this.withGreeting(transcript.map(transcriptMessage));
        } catch (error) {
          if (!(error instanceof WidgetApiError) || error.status !== 401) throw error;
          this.clearStoredSession();
          await this.bootstrap();
        }
      } else {
        await this.bootstrap();
      }
      this.initialized = true;
      this.transcript.setAttribute("aria-busy", "false");
      this.renderMessages();
      this.updateComposerState();
    } catch {
      this.renderInitializationError();
    }
  }

  private async bootstrap(): Promise<void> {
    const createdSession = await createSession(this.apiBase, this.agentId);
    const conversation = await createConversation(this.apiBase, createdSession.access_token);
    this.config = createdSession.config;
    this.applyConfig(createdSession.config);
    this.session = {
      token: createdSession.access_token,
      expiresAt: createdSession.expires_at,
      conversationId: conversation.public_id,
      config: createdSession.config,
    };
    this.messages = this.withGreeting([]);
    this.persistSession();
  }

  private withGreeting(messages: WidgetMessage[]): WidgetMessage[] {
    if (!this.config?.greeting) return messages;
    return [{
      id: "configured-greeting",
      role: "assistant",
      text: this.config.greeting,
      state: "complete",
      products: [],
      sources: [],
    }, ...messages];
  }

  private applyConfig(config: WidgetConfig): void {
    const color = /^#[0-9A-Fa-f]{6}$/.test(config.brand_color)
      ? config.brand_color
      : "#0F8F87";
    this.host.style.setProperty("--ah-brand", color, "important");
    const position = config.launcher_position === "left" ? "left" : "right";
    this.host.dataset.position = position;
    this.protectHost(position);
    this.title.textContent = config.display_name || "Trợ lý cửa hàng";
    this.uploadButton.hidden = !config.capabilities.image_input;
  }

  private protectHost(position: "left" | "right"): void {
    const mobile = typeof window.matchMedia === "function"
      && window.matchMedia("(max-width: 480px)").matches;
    const fixed: Record<string, string> = {
      all: "initial",
      display: "block",
      position: "fixed",
      "z-index": "2147483000",
      bottom: mobile ? "10px" : "18px",
      top: "auto",
      width: mobile ? "calc(100vw - 20px)" : "auto",
      height: "auto",
      margin: "0",
      padding: "0",
      border: "0",
      background: "transparent",
      color: "#10212b",
      "color-scheme": "light",
      "font-family": "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
      "font-size": "14px",
      "line-height": "1.45",
    };
    for (const [property, value] of Object.entries(fixed)) {
      this.host.style.setProperty(property, value, "important");
    }
    this.host.style.setProperty(
      "right",
      !mobile && position === "right" ? "18px" : "auto",
      "important",
    );
    this.host.style.setProperty(
      "left",
      mobile ? "10px" : position === "left" ? "18px" : "auto",
      "important",
    );
  }

  private setOpen(value: boolean): void {
    this.open = value;
    this.panel.hidden = !value;
    this.launcher.setAttribute("aria-expanded", String(value));
    this.launcher.setAttribute(
      "aria-label",
      value ? "Đóng trợ lý mua sắm" : "Mở trợ lý mua sắm",
    );
    if (value) {
      if (!this.initialization) this.initialization = this.initialize();
      queueMicrotask(() => this.textarea.focus());
    } else {
      this.launcher.focus();
    }
  }

  private renderLoading(): void {
    this.transcript.replaceChildren();
    const loading = element("div", "ah-loading");
    loading.append(
      element("span", "ah-loading-dot"),
      element("span", undefined, "Đang kết nối với trợ lý…"),
    );
    this.transcript.append(loading);
  }

  private renderInitializationError(): void {
    this.initialized = false;
    this.transcript.setAttribute("aria-busy", "false");
    this.transcript.replaceChildren();
    const state = element("div", "ah-empty-error");
    state.append(
      element("strong", undefined, "Chưa thể mở trợ lý"),
      element("span", undefined, "Vui lòng kiểm tra kết nối rồi thử lại."),
    );
    const retry = element("button", "ah-retry", "Thử lại");
    retry.type = "button";
    retry.addEventListener("click", () => {
      this.initialization = this.initialize();
    });
    state.append(retry);
    this.transcript.append(state);
    this.updateComposerState();
  }

  private renderMessages(): void {
    this.transcript.replaceChildren();
    for (const message of this.messages) {
      const article = element("article", `ah-message ${message.role} ${message.state}`);
      const bubble = element("div", "ah-bubble");
      if (message.localImageUrl) {
        const image = element("img", "ah-message-image");
        image.src = message.localImageUrl;
        image.alt = "Ảnh sản phẩm đã gửi";
        bubble.append(image);
      }
      if (message.text) bubble.append(element("span", undefined, message.text));
      if (message.state === "streaming" && !message.text) {
        const typing = element("span", "ah-typing");
        typing.setAttribute("aria-label", "Đang tạo câu trả lời");
        typing.append(element("i"), element("i"), element("i"));
        bubble.append(typing);
      }
      article.append(bubble);
      if (message.products.length) article.append(this.renderProducts(message.products));
      if (message.sources.length) article.append(this.renderSources(message.sources));
      this.transcript.append(article);
    }
    const hasVisitorMessage = this.messages.some((message) => message.role === "user");
    this.suggestions.hidden = hasVisitorMessage || !this.initialized;
    this.transcript.scrollTop = this.transcript.scrollHeight;
    void this.hydrateProductImages();
  }

  private renderProducts(cards: PublicProductCard[]): HTMLElement {
    const list = element("div", "ah-products");
    for (const card of cards) {
      const article = element("article", "ah-product");
      const image = element("div", "ah-product-image", "◇");
      const firstImage = card.images[0];
      if (firstImage) {
        image.dataset.publicImage = firstImage.url;
        image.setAttribute("aria-label", firstImage.alt_text ?? card.name);
      } else {
        image.setAttribute("aria-label", "Chưa có ảnh sản phẩm");
      }
      const copy = element("div", "ah-product-copy");
      copy.append(
        element("small", undefined, card.sku ?? "Không có SKU"),
        element("strong", undefined, card.name),
        element("span", "ah-price", priceLabel(card)),
      );
      const stock = stockLabel(card);
      copy.append(element("span", `ah-stock ${stock.available ? "available" : ""}`, stock.text));
      const options = Object.entries(card.options).slice(0, 2);
      if (options.length) {
        copy.append(element(
          "p",
          "ah-options",
          options.map(([name, values]) => `${name}: ${values.join(", ")}`).join(" · "),
        ));
      }
      if (card.product_url) {
        const link = element("a", undefined, "Xem sản phẩm →");
        link.href = card.product_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        copy.append(link);
      }
      article.append(image, copy);
      list.append(article);
    }
    return list;
  }

  private renderSources(sources: PublicSource[]): HTMLElement {
    const details = element("details", "ah-sources");
    details.append(element("summary", undefined, `Nguồn tham khảo (${sources.length})`));
    const list = element("ul");
    for (const source of sources) {
      list.append(element("li", undefined, `${source.title} · ${source.locator}`));
    }
    details.append(list);
    return details;
  }

  private async hydrateProductImages(): Promise<void> {
    if (!this.session) return;
    const containers = Array.from(
      this.transcript.querySelectorAll<HTMLElement>("[data-public-image]"),
    );
    await Promise.all(containers.map(async (container) => {
      const path = container.dataset.publicImage;
      if (!path) return;
      let objectUrl = this.imageUrls.get(path);
      if (!objectUrl) {
        try {
          const blob = await fetchProductImage(this.apiBase, this.session!.token, path);
          if (!blob.type.startsWith("image/") || blob.size > 10 * 1024 * 1024) return;
          objectUrl = URL.createObjectURL(blob);
          this.imageUrls.set(path, objectUrl);
          this.objectUrls.add(objectUrl);
        } catch {
          return;
        }
      }
      if (!container.isConnected || container.dataset.publicImage !== path) return;
      const image = element("img");
      image.src = objectUrl;
      image.alt = container.getAttribute("aria-label") ?? "Ảnh sản phẩm";
      container.replaceChildren(image);
    }));
  }

  private showError(message?: string): void {
    this.error.textContent = message ?? "";
    this.error.hidden = !message;
  }

  private updateComposerState(): void {
    const send = this.composer.querySelector<HTMLButtonElement>(".ah-send:not(.ah-stop)");
    if (send) {
      send.disabled = !this.initialized
        || Boolean(this.activeController)
        || Boolean(this.pendingAttachment?.uploading)
        || (!this.textarea.value.trim() && !this.pendingAttachment?.attachmentId);
    }
    this.uploadButton.disabled = !this.initialized
      || Boolean(this.activeController)
      || Boolean(this.pendingAttachment);
  }

  private async selectImage(): Promise<void> {
    const file = this.fileInput.files?.[0];
    this.fileInput.value = "";
    if (!file || !this.session || !this.config?.capabilities.image_input) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      this.showError("Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.showError("Ảnh không được vượt quá 5 MiB.");
      return;
    }
    const previewUrl = URL.createObjectURL(file);
    this.objectUrls.add(previewUrl);
    this.pendingAttachment = {
      fileName: file.name,
      previewUrl,
      uploading: true,
    };
    this.renderAttachment();
    this.updateComposerState();
    this.showError();
    try {
      const uploaded = await uploadImage(this.apiBase, this.session.token, file);
      if (!this.pendingAttachment || this.pendingAttachment.previewUrl !== previewUrl) return;
      this.pendingAttachment.attachmentId = uploaded.attachment_id;
      this.pendingAttachment.uploading = false;
      this.renderAttachment();
    } catch (error) {
      this.removePendingAttachment(false);
      this.showError(error instanceof WidgetApiError
        ? error.message
        : "Không thể tải ảnh. Vui lòng thử lại.");
    } finally {
      this.updateComposerState();
    }
  }

  private renderAttachment(): void {
    const pending = this.pendingAttachment;
    this.attachment.replaceChildren();
    this.attachment.hidden = !pending;
    if (!pending) return;
    const image = element("img");
    image.src = pending.previewUrl;
    image.alt = "Ảnh chuẩn bị gửi";
    const label = element(
      "span",
      undefined,
      pending.uploading ? "Đang tải ảnh an toàn…" : pending.fileName,
    );
    const remove = element("button", undefined, "×");
    remove.type = "button";
    remove.disabled = pending.uploading;
    remove.setAttribute("aria-label", "Gỡ ảnh đính kèm");
    remove.addEventListener("click", () => this.removePendingAttachment(true));
    this.attachment.append(image, label, remove);
  }

  private removePendingAttachment(removeRemote: boolean): void {
    const pending = this.pendingAttachment;
    this.pendingAttachment = undefined;
    this.attachment.hidden = true;
    this.attachment.replaceChildren();
    if (!pending) return;
    if (removeRemote && pending.attachmentId && this.session) {
      void deleteImage(this.apiBase, this.session.token, pending.attachmentId).catch(() => undefined);
    }
    URL.revokeObjectURL(pending.previewUrl);
    this.objectUrls.delete(pending.previewUrl);
    this.updateComposerState();
  }

  private async send(): Promise<void> {
    if (!this.initialized || !this.session || this.activeController) return;
    const attachment = this.pendingAttachment;
    if (attachment?.uploading || (attachment && !attachment.attachmentId)) return;
    const text = this.textarea.value.trim()
      || (attachment ? "Tìm sản phẩm tương tự trong cửa hàng" : "");
    if (!text) return;
    const assistantId = crypto.randomUUID();
    this.messages.push({
      id: crypto.randomUUID(),
      role: "user",
      text,
      state: "complete",
      products: [],
      sources: [],
      localImageUrl: attachment?.previewUrl,
    }, {
      id: assistantId,
      role: "assistant",
      text: "",
      state: "streaming",
      products: [],
      sources: [],
    });
    this.pendingAttachment = undefined;
    this.attachment.hidden = true;
    this.attachment.replaceChildren();
    this.textarea.value = "";
    this.showError();
    this.activeController = new AbortController();
    this.composer.classList.add("streaming");
    this.renderMessages();
    this.updateComposerState();
    const idempotencyKey = crypto.randomUUID();
    try {
      await streamMessage(
        this.apiBase,
        this.session.token,
        this.session.conversationId,
        {
          message: text,
          ...(attachment?.attachmentId ? { attachment_id: attachment.attachmentId } : {}),
        },
        idempotencyKey,
        (event) => this.handleStreamEvent(assistantId, event),
        this.activeController.signal,
      );
    } catch (error) {
      const assistant = this.messages.find((message) => message.id === assistantId);
      if (assistant) {
        if (error instanceof DOMException && error.name === "AbortError") {
          assistant.state = "cancelled";
          assistant.text ||= "Đã dừng tạo câu trả lời.";
        } else {
          assistant.state = "complete";
          assistant.text ||= "Mình chưa thể kết nối lúc này. Bạn thử lại sau một chút nhé.";
          this.showError("Kết nối bị gián đoạn. Tin nhắn của bạn vẫn được giữ lại.");
        }
      }
    } finally {
      this.activeController = undefined;
      this.composer.classList.remove("streaming");
      this.renderMessages();
      this.updateComposerState();
    }
  }

  private handleStreamEvent(
    assistantId: string,
    event: Parameters<typeof streamMessage>[5] extends (value: infer T) => void ? T : never,
  ): void {
    const assistant = this.messages.find((message) => message.id === assistantId);
    if (!assistant) return;
    if (event.type === "message.delta") assistant.text += event.data.text;
    if (event.type === "product.cards") assistant.products = event.data.items;
    if (event.type === "source.refs") assistant.sources = event.data.items;
    if (event.type === "message.completed") assistant.state = "complete";
    if (event.type !== "heartbeat" && event.type !== "message.start") this.renderMessages();
  }

  private async resetConversation(): Promise<void> {
    if (!this.session) return;
    if (!window.confirm("Xóa cuộc trò chuyện này và bắt đầu lại?")) return;
    this.activeController?.abort();
    this.showError();
    try {
      await deleteConversation(
        this.apiBase,
        this.session.token,
        this.session.conversationId,
      );
      this.clearStoredSession();
      for (const url of this.objectUrls) URL.revokeObjectURL(url);
      this.objectUrls.clear();
      this.imageUrls.clear();
      this.messages = [];
      this.initialization = this.initialize(true);
      await this.initialization;
    } catch (error) {
      this.showError(error instanceof WidgetApiError
        ? error.message
        : "Không thể xóa cuộc trò chuyện lúc này.");
    }
  }
}
