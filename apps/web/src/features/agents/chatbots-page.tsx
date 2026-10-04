"use client";

import {
  Bot,
  Boxes,
  Globe2,
  LoaderCircle,
  MapPin,
  MessageSquareText,
  Plus,
  Save,
  X,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { FeedbackBanner } from "@/components/feedback-banner";
import { ChatbotPlayground } from "@/features/agents/chatbot-playground";
import { WebChannelPanel } from "@/features/agents/web-channel-panel";
import {
  api,
  type Agent,
  type CatalogCollection,
  type KnowledgeBase,
  type Location,
} from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";

type AgentDraft = {
  name: string;
  greeting: string;
  safeInstructions: string;
  defaultLocale: string;
  allLocations: boolean;
  locationIds: number[];
  allCollections: boolean;
  collectionIds: number[];
  knowledgeBaseIds: number[];
};

function draftFrom(agent: Agent, knowledgeBaseIds: number[] = []): AgentDraft {
  return {
    name: agent.name,
    greeting: agent.greeting ?? "",
    safeInstructions: agent.safe_instructions ?? "",
    defaultLocale: agent.default_locale,
    allLocations: agent.catalog_scope.location_ids === null,
    locationIds: agent.catalog_scope.location_ids ?? [],
    allCollections: agent.catalog_scope.collection_ids === null,
    collectionIds: agent.catalog_scope.collection_ids ?? [],
    knowledgeBaseIds,
  };
}

export function ChatbotsPage() {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [requestedAgentId] = useState(() => searchParams.get("agent") ?? undefined);
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [collections, setCollections] = useState<CatalogCollection[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [draft, setDraft] = useState<AgentDraft>();
  const [draftAgentId, setDraftAgentId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"create" | "save">();
  const [pageFeedback, setPageFeedback] = useState<UiFeedback>();
  const [dirty, setDirty] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [mobileTab, setMobileTab] = useState<"config" | "chat">("chat");
  const [activeView, setActiveView] = useState<"workbench" | "web">("workbench");
  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";
  const selectedAgent = agents.find((item) => item.public_id === selectedId);

  function selectAvailableAgent(items: Agent[], preferredId?: string) {
    const nextId = preferredId && items.some((item) => item.public_id === preferredId)
      ? preferredId
      : items[0]?.public_id;
    setSelectedId(nextId);
    return nextId;
  }

  async function loadAgents(workspaceId: string, preferredId?: string) {
    const result = await api.listAgents(workspaceId);
    setAgents(result.items);
    if (result.items.length === 0) {
      setDraft(undefined);
      setDraftAgentId(undefined);
    }
    selectAvailableAgent(result.items, preferredId ?? selectedId);
    return result.items;
  }

  useEffect(() => {
    if (!workspace) return;
    let active = true;
    Promise.all([
      api.listAgents(workspace.id),
      api.listKnowledgeBases(workspace.id),
      api.listLocations(workspace.id),
      api.listCollections(workspace.id),
    ]).then(([agentResult, bases, locationItems, collectionItems]) => {
      if (!active) return;
      setDraft(undefined);
      setDraftAgentId(undefined);
      setDirty(false);
      setSavedNotice(false);
      setAgents(agentResult.items);
      selectAvailableAgent(agentResult.items, requestedAgentId);
      setKnowledgeBases(bases.items);
      setLocations(locationItems.filter((item) => item.is_active));
      setCollections(collectionItems.filter((item) => item.is_active));
    }).catch((caught) => {
      if (active) {
        setPageFeedback(toUiError(caught, {
          operation: "agents.load-page",
          fallback: "Không thể tải cấu hình chatbot. Vui lòng thử lại.",
        }));
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [requestedAgentId, workspace]);

  useEffect(() => {
    if (!workspace || !selectedAgent) return;
    let active = true;
    api.getAgentKnowledgeBases(workspace.id, selectedAgent.public_id).then((result) => {
      if (!active) return;
      setDraft(draftFrom(selectedAgent, result.knowledge_base_ids));
      setDraftAgentId(selectedAgent.public_id);
    }).catch((caught) => {
      if (active) {
        setPageFeedback(toUiError(caught, {
          operation: "agents.load-knowledge-scope",
          fallback: "Không thể tải nguồn tri thức của chatbot.",
        }));
      }
    });
    return () => { active = false; };
  }, [selectedAgent, workspace]);

  function selectAgent(publicId: string) {
    setDraft(undefined);
    setDraftAgentId(undefined);
    setDirty(false);
    setSavedNotice(false);
    setSelectedId(publicId);
    setActiveView("workbench");
    router.replace(`/app/${encodeURIComponent(params.workspaceSlug)}/chatbots?agent=${encodeURIComponent(publicId)}`, { scroll: false });
  }

  function openWebChannel() {
    if (dirty && !window.confirm(
      "Bỏ thay đổi cấu hình chatbot chưa lưu để mở kênh Web?",
    )) return;
    if (dirty && selectedAgent) {
      setDraft(draftFrom(selectedAgent, draft?.knowledgeBaseIds));
      setDirty(false);
    }
    setActiveView("web");
  }

  function updateDraft(update: Partial<AgentDraft>) {
    setSavedNotice(false);
    setDirty(true);
    setDraft((current) => current ? { ...current, ...update } : current);
  }

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy("create");
    setPageFeedback(undefined);
    try {
      const created = await api.createAgent(workspace.id, {
        name: String(form.get("name")),
        default_locale: "vi",
      });
      setAgents((current) => [created, ...current.filter((item) => item.public_id !== created.public_id)]);
      formElement.reset();
      setShowCreate(false);
      selectAgent(created.public_id);
      setPageFeedback(feedback("success", "Đã tạo chatbot. Bạn có thể cấu hình và thử ngay bây giờ."));
    } catch (caught) {
      setPageFeedback(toUiError(caught, {
        operation: "agents.create",
        fallback: "Không thể tạo chatbot. Tên bạn đã nhập vẫn được giữ lại.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selectedAgent || !draft || !dirty) return;
    setBusy("save");
    setSavedNotice(false);
    setPageFeedback(undefined);
    let completedWrites = 0;
    try {
      await api.updateAgent(workspace.id, selectedAgent.public_id, {
        name: draft.name,
        greeting: draft.greeting || null,
        safe_instructions: draft.safeInstructions || null,
        default_locale: draft.defaultLocale,
      });
      completedWrites += 1;
      await api.replaceAgentCatalogScope(workspace.id, selectedAgent.public_id, {
        location_ids: draft.allLocations ? null : draft.locationIds,
        collection_ids: draft.allCollections ? null : draft.collectionIds,
      });
      completedWrites += 1;
      await api.replaceAgentKnowledgeBases(
        workspace.id,
        selectedAgent.public_id,
        draft.knowledgeBaseIds,
      );
      completedWrites += 1;
      setDirty(false);
      setSavedNotice(true);
      try {
        await loadAgents(workspace.id, selectedAgent.public_id);
      } catch (caught) {
        setSavedNotice(false);
        const refreshError = toUiError(caught, {
          operation: "agents.refresh-after-save",
          fallback: "Đã lưu cấu hình, nhưng chưa thể làm mới dữ liệu hiển thị.",
        });
        setPageFeedback({
          ...refreshError,
          kind: "warning",
          message: "Đã lưu cấu hình, nhưng dữ liệu hiển thị có thể chưa mới nhất. Hãy tải lại trang.",
        });
      }
    } catch (caught) {
      const saveError = toUiError(caught, {
        operation: "agents.save",
        fallback: "Không thể lưu cấu hình chatbot. Vui lòng thử lại.",
      });
      setPageFeedback(completedWrites > 0 ? {
        ...saveError,
        kind: "warning",
        message: "Chỉ một phần cấu hình đã được lưu. Vui lòng kiểm tra và lưu lại.",
      } : saveError);
    } finally {
      setBusy(undefined);
    }
  }

  function toggleId(field: "locationIds" | "collectionIds" | "knowledgeBaseIds", id: number) {
    if (!draft) return;
    const values = draft[field];
    updateDraft({ [field]: values.includes(id) ? values.filter((item) => item !== id) : [...values, id] });
  }

  if (workspaceError) return <main className="center-state"><FeedbackBanner feedback={workspaceError} onRetry={() => location.reload()} /></main>;
  if (!me || !workspace) return <main className="center-state" aria-live="polite">Đang tải cửa hàng…</main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="page-heading chatbot-page-heading">
        <div><p className="eyebrow">Trợ lý AI</p><h1>Chatbot</h1><p>Quản lý cấu hình và thử phản hồi bằng dữ liệu thật trên cùng một màn hình.</p></div>
        <div className="chatbot-heading-actions">
          {!canWrite && <span className="status-pill archived">Chỉ đọc</span>}
          {canWrite && <button className="secondary-button" onClick={() => setShowCreate((current) => !current)} type="button">{showCreate ? <X size={16} /> : <Plus size={16} />}{showCreate ? "Đóng" : "Tạo chatbot"}</button>}
        </div>
      </section>
      {showCreate && canWrite && <form className="chatbot-create-bar" onSubmit={createAgent}><label><span>Tên chatbot mới</span><input maxLength={160} name="name" placeholder="Ví dụ: Trợ lý ND Shop" required /></label><button className="primary-button compact-button" disabled={busy === "create"} type="submit">{busy === "create" ? <LoaderCircle className="spinner" size={16} /> : <Plus size={16} />} Tạo chatbot</button></form>}
      {pageFeedback && <FeedbackBanner feedback={pageFeedback} />}
      {savedNotice && <p className="success-message" role="status">Đã lưu cấu hình chatbot.</p>}
      {loading && <section className="chatbot-page-state"><LoaderCircle className="spinner" size={20} /> Đang tải cấu hình…</section>}
      {!loading && agents.length === 0 && <section className="chatbot-page-state"><Bot size={30} /><h2>Chưa có chatbot</h2><p>Tạo chatbot đầu tiên để cấu hình nguồn dữ liệu và thử phản hồi ngay trên màn hình này.</p>{canWrite && <button className="primary-button compact-button" onClick={() => setShowCreate(true)} type="button"><Plus size={16} /> Tạo chatbot đầu tiên</button>}</section>}
      {!loading && selectedAgent && (
        <>
          <section className="chatbot-agent-strip">
            <span className="agent-avatar" aria-hidden="true"><Bot size={18} /></span>
            <div className="chatbot-agent-copy"><strong>{selectedAgent.name}</strong><small>{selectedAgent.status === "published" ? "Đã phát hành" : selectedAgent.status === "paused" ? "Đã tạm dừng" : "Bản nháp"} · Catalog và {draft?.knowledgeBaseIds.length ?? 0} nguồn tri thức đang được dùng</small></div>
            <div className="chatbot-agent-actions">
              {dirty && <span className="status-pill pending">Có thay đổi chưa lưu</span>}
              <div className="chatbot-view-switch" aria-label="Khu vực chatbot" role="group"><button aria-pressed={activeView === "workbench"} onClick={() => setActiveView("workbench")} type="button"><Bot size={15} /> Cấu hình & thử</button><button aria-pressed={activeView === "web"} onClick={openWebChannel} type="button"><Globe2 size={15} /> Kênh Web</button></div>
              <label className="chatbot-agent-select"><span className="sr-only">Đổi chatbot</span><select aria-label="Đổi chatbot" onChange={(event) => selectAgent(event.target.value)} value={selectedId}>{agents.map((agent) => <option key={agent.public_id} value={agent.public_id}>{agent.name}</option>)}</select></label>
              {canWrite && <button aria-label="Tạo chatbot" className="icon-button" onClick={() => setShowCreate(true)} type="button"><Plus size={16} /></button>}
            </div>
          </section>
          {activeView === "workbench" && <><div className="chatbot-mobile-tabs" role="tablist">
            <button aria-selected={mobileTab === "config"} onClick={() => setMobileTab("config")} role="tab" type="button">Cấu hình</button>
            <button aria-selected={mobileTab === "chat"} onClick={() => setMobileTab("chat")} role="tab" type="button">Thử chatbot</button>
          </div>
          <div className="chatbot-workbench">
            <section className={`agent-config-card chatbot-config-panel ${mobileTab === "config" ? "mobile-active" : ""}`}>
              {!draft || draftAgentId !== selectedAgent.public_id ? <p className="compact-empty"><LoaderCircle className="spinner" size={18} /> Đang tải cấu hình…</p> : (
                <form onSubmit={saveAgent}>
                  <div className="card-heading agent-config-heading"><div><h2>Cấu hình</h2><p>Thay đổi áp dụng cho bản nháp sau khi lưu</p></div>{dirty && <span className="status-pill pending">Chưa lưu</span>}</div>
                  <div className="agent-config-sections">
                    <fieldset className="agent-fieldset" disabled={!canWrite}><legend>Thông tin và hành vi</legend><label>Tên<input maxLength={160} onChange={(event) => updateDraft({ name: event.target.value })} required value={draft.name} /></label><label>Ngôn ngữ<select onChange={(event) => updateDraft({ defaultLocale: event.target.value })} value={draft.defaultLocale}><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label><label className="full-field">Lời chào<textarea maxLength={2000} onChange={(event) => updateDraft({ greeting: event.target.value })} rows={3} value={draft.greeting} /></label><label className="full-field">Tính cách và phong cách trả lời<small className="agent-field-help">Chatbot mới đã có cấu hình thân thiện để dùng ngay. Bạn có thể chỉnh cách xưng hô, độ dài và phong cách tư vấn tại đây.</small><textarea maxLength={10000} onChange={(event) => updateDraft({ safeInstructions: event.target.value })} placeholder="Ví dụ: Xưng hô gần gũi, tư vấn ngắn gọn và luôn hỏi thêm nhu cầu của khách." rows={5} value={draft.safeInstructions} /></label></fieldset>
                    <fieldset className="agent-fieldset" disabled={!canWrite}><legend><MessageSquareText aria-hidden="true" size={17} /> Nguồn tri thức</legend><p className="fieldset-help">Chỉ dữ liệu đã ingestion thành công mới được runtime truy xuất.</p><div className="scope-options">{knowledgeBases.map((base) => <label className="check-option" key={base.id}><input checked={draft.knowledgeBaseIds.includes(base.id)} onChange={() => toggleId("knowledgeBaseIds", base.id)} type="checkbox" /><span><strong>{base.name}</strong><small>{base.document_count} tài liệu · {base.kind}</small></span></label>)}{knowledgeBases.length === 0 && <p className="muted-copy">Chưa có kho tri thức.</p>}</div></fieldset>
                    <fieldset className="agent-fieldset" disabled={!canWrite}><legend><MapPin aria-hidden="true" size={17} /> Phạm vi location</legend><label className="check-option"><input checked={draft.allLocations} onChange={(event) => updateDraft({ allLocations: event.target.checked })} type="checkbox" /><span><strong>Tất cả location đang hoạt động</strong><small>Tự động bao gồm location mới.</small></span></label>{!draft.allLocations && <div className="scope-options">{locations.map((location) => <label className="check-option" key={location.id}><input checked={draft.locationIds.includes(location.id)} onChange={() => toggleId("locationIds", location.id)} type="checkbox" /><span>{location.name}</span></label>)}</div>}</fieldset>
                    <fieldset className="agent-fieldset" disabled={!canWrite}><legend><Boxes aria-hidden="true" size={17} /> Phạm vi collection</legend><label className="check-option"><input checked={draft.allCollections} onChange={(event) => updateDraft({ allCollections: event.target.checked })} type="checkbox" /><span><strong>Tất cả collection đang hoạt động</strong><small>Tự động bao gồm collection mới.</small></span></label>{!draft.allCollections && <div className="scope-options">{collections.map((collection) => <label className="check-option" key={collection.id}><input checked={draft.collectionIds.includes(collection.id)} onChange={() => toggleId("collectionIds", collection.id)} type="checkbox" /><span>{collection.name}</span></label>)}</div>}</fieldset>
                  </div>
                  {canWrite && <div className="agent-save-bar"><span>{dirty ? "Có thay đổi chưa lưu" : "Cấu hình đã đồng bộ"}</span><button className="primary-button compact-button" disabled={busy === "save" || !dirty} type="submit">{busy === "save" ? <LoaderCircle className="spinner" size={16} /> : <Save size={16} />} Lưu cấu hình</button></div>}
                </form>
              )}
            </section>
            <div className={`chatbot-playground-panel ${mobileTab === "chat" ? "mobile-active" : ""}`}><ChatbotPlayground agent={selectedAgent} key={selectedAgent.public_id} workspaceId={workspace.id} /></div>
          </div></>}
          {activeView === "web" && <WebChannelPanel canWrite={canWrite} key={selectedAgent.public_id} onChanged={() => loadAgents(workspace.id, selectedAgent.public_id)} publicAgentId={selectedAgent.public_id} workspaceId={workspace.id} />}
        </>
      )}
    </AppShell>
  );
}
