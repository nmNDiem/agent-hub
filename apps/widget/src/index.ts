import { AgentHubWidget } from "./widget";

export const WIDGET_PACKAGE_STATUS = "functional" as const;

export interface WidgetPackageInfo {
  readonly status: typeof WIDGET_PACKAGE_STATUS;
  readonly functional: true;
}

export function getWidgetPackageInfo(): WidgetPackageInfo {
  return { status: WIDGET_PACKAGE_STATUS, functional: true };
}

export function mountWidget(options: {
  agentId: string;
  apiBase: string;
  target?: HTMLElement;
}): AgentHubWidget {
  const agentId = options.agentId.trim().toLowerCase();
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(agentId)) {
    throw new Error("AgentHub widget requires a UUIDv7 agent ID");
  }
  const apiUrl = new URL(options.apiBase);
  if (!["http:", "https:"].includes(apiUrl.protocol) || apiUrl.username || apiUrl.password) {
    throw new Error("AgentHub widget requires an HTTP(S) API origin");
  }
  const apiBase = apiUrl.origin;
  const host = options.target ?? document.createElement("div");
  if (!options.target) document.body.append(host);
  host.dataset.agentHubWidget = agentId;
  return new AgentHubWidget(host, agentId, apiBase);
}

function autoMount(): void {
  const script = document.currentScript;
  if (!(script instanceof HTMLScriptElement)) return;
  const agentId = script.dataset.agentId;
  if (!agentId) return;
  if (document.querySelector(`[data-agent-hub-widget="${CSS.escape(agentId.toLowerCase())}"]`)) {
    return;
  }
  const apiBase = script.dataset.apiBase || new URL(script.src, document.baseURI).origin;
  try {
    mountWidget({ agentId, apiBase });
  } catch {
    // Invalid public embed configuration fails closed without affecting the host page.
  }
}

if (typeof document !== "undefined") autoMount();
