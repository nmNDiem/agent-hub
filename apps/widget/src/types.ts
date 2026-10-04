export type WidgetConfig = {
  display_name: string;
  greeting: string | null;
  brand_color: string;
  launcher_position: "left" | "right";
  capabilities: { image_input: boolean };
  contact: {
    handoff_url: string | null;
    handoff_label: string | null;
    consent_text: string;
    consent_text_version: string;
    lead_retention_days: number;
  };
};

export type LeadCapturePayload = {
  name: string | null;
  email: string | null;
  phone: string | null;
  consent_given: true;
  consent_text_version: string;
};

export type LeadCaptureResponse = {
  status: "received";
  followup_status: "new" | "contacted" | "closed";
  retention_until: string;
};

export type WidgetSession = {
  access_token: string;
  expires_at: string;
  config: WidgetConfig;
};

export type WidgetConversation = {
  public_id: string;
  status: "open" | "deleted";
  retention_until: string;
};

export type PublicProductImage = { url: string; alt_text: string | null };

export type PublicProductCard = {
  card_id: string;
  sku: string | null;
  name: string;
  product_url: string | null;
  currency: string;
  price: { kind: "exact" | "range" | "unknown"; minimum: string | null; maximum: string | null };
  availability: {
    total_locations: number;
    in_stock_locations: number;
    out_of_stock_locations: number;
    unknown_locations: number;
  };
  options: Record<string, string[]>;
  attributes: Record<string, unknown>;
  variants: Array<{
    sku: string | null;
    name: string | null;
    options: Record<string, string>;
    attributes: Record<string, unknown>;
    inventory_state: "in_stock" | "out_of_stock" | "unknown";
  }>;
  images: PublicProductImage[];
};

export type PublicSource = { source_id: string; title: string; locator: string };

export type TranscriptItem = {
  role: "user" | "assistant";
  text: string;
  status: "pending" | "completed" | "failed" | "cancelled";
  response_id: string | null;
  product_cards: PublicProductCard[];
  sources: PublicSource[];
  created_at: string;
};

export type WidgetStreamEvent =
  | { type: "heartbeat"; data: Record<string, never> }
  | { type: "message.start"; data: { message_id: string } }
  | { type: "message.delta"; data: { text: string } }
  | { type: "product.cards"; data: { items: PublicProductCard[] } }
  | { type: "source.refs"; data: { items: PublicSource[] } }
  | { type: "message.completed"; data: { message_id: string; usage: Record<string, number> } };

export type AttachmentUpload = {
  attachment_id: string;
  content_type: "image/jpeg" | "image/png" | "image/webp";
  width: number;
  height: number;
  expires_at: string;
};

export type WidgetMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  state: "complete" | "streaming" | "cancelled";
  products: PublicProductCard[];
  sources: PublicSource[];
  localImageUrl?: string;
};
