"use client";

import {
  Bot,
  Boxes,
  ChevronDown,
  ChevronUp,
  Globe2,
  LoaderCircle,
  MapPin,
  MessagesSquare,
  MessageSquareText,
  PhoneForwarded,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { FeedbackBanner } from "@/components/feedback-banner";
import {
  AGENT_GLYPH_COLOR,
  AGENT_ICON_OPTIONS,
  AgentGlyph,
} from "@/features/agents/agent-appearance";
import { ChatbotPlayground } from "@/features/agents/chatbot-playground";
import { FacebookChannelPanel } from "@/features/agents/facebook-channel-panel";
import { WebChannelPanel } from "@/features/agents/web-channel-panel";
import { ZaloChannelPanel } from "@/features/agents/zalo-channel-panel";
import {
  api,
  type Agent,
  type AgentIcon,
  type CatalogCollection,
  type KnowledgeBase,
  type Location,
  type IntakeDefinition,
  type IntakeField,
  type IntakeFieldSemantic,
} from "@/lib/api";
import { feedback, toUiError, type UiFeedback } from "@/lib/errors";
import { useWorkspace } from "@/lib/use-workspace";
import { useWorkspaceSystem } from "@/lib/workspace-system-context";

type AgentDraft = {
  name: string;
  icon: AgentIcon;
  color: string;
  greeting: string;
  safeInstructions: string;
  defaultLocale: string;
  allLocations: boolean;
  locationIds: number[];
  allCollections: boolean;
  collectionIds: number[];
  knowledgeBaseIds: number[];
  followUpActionEnabled: boolean;
  intakeActionEnabled: boolean;
  intakeDefinition: IntakeDefinition;
};

const intakeSemantics: Array<{ value: IntakeFieldSemantic; label: string }> = [
  { value: "name", label: "Tên khách" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Số điện thoại" },
  { value: "service_category", label: "Nhóm dịch vụ" },
  { value: "service_area", label: "Khu vực" },
  { value: "preferred_date", label: "Ngày mong muốn" },
  { value: "preference", label: "Ưu tiên" },
  { value: "context", label: "Bối cảnh" },
];

function fieldFor(semantic: IntakeFieldSemantic): IntakeField {
  const names: Record<IntakeFieldSemantic, string> = {
    name: "Tên của bạn",
    email: "Email liên hệ",
    phone: "Số điện thoại",
    service_category: "Dịch vụ quan tâm",
    service_area: "Khu vực cần hỗ trợ",
    preferred_date: "Ngày mong muốn",
    preference: "Ưu tiên của bạn",
    context: "Thông tin cần lưu ý",
  };
  const kinds: Record<IntakeFieldSemantic, IntakeField["kind"]> = {
    name: "short_text",
    email: "email",
    phone: "phone",
    service_category: "single_choice",
    service_area: "short_text",
    preferred_date: "date",
    preference: "long_text",
    context: "long_text",
  };
  return {
    key: null,
    semantic,
    label: names[semantic],
    help_text: null,
    kind: kinds[semantic],
    required: semantic === "email",
    options: semantic === "service_category"
      ? [{ key: null, label: "Tư vấn" }, { key: null, label: "Báo giá" }]
      : [],
  };
}

function defaultIntakeDefinition(): IntakeDefinition {
  return {
    purpose: "Tư vấn và liên hệ lại theo nhu cầu của khách",
    disclosure: "Mình xin phép ghi nhận các thông tin này để đội ngũ tư vấn hỗ trợ bạn tốt hơn nhé.",
    disclosure_version: null,
    fields: [fieldFor("name"), fieldFor("email"), fieldFor("context")],
  };
}

function draftFrom(agent: Agent, knowledgeBaseIds: number[] = []): AgentDraft {
  return {
    name: agent.name,
    icon: agent.icon,
    color: agent.color,
    greeting: agent.greeting ?? "",
    safeInstructions: agent.safe_instructions ?? "",
    defaultLocale: agent.default_locale,
    allLocations: agent.catalog_scope.location_ids === null,
    locationIds: agent.catalog_scope.location_ids ?? [],
    allCollections: agent.catalog_scope.collection_ids === null,
    collectionIds: agent.catalog_scope.collection_ids ?? [],
    knowledgeBaseIds,
    followUpActionEnabled: agent.follow_up_action_enabled,
    intakeActionEnabled: agent.intake_action_enabled,
    intakeDefinition: agent.intake_definition ?? defaultIntakeDefinition(),
  };
}

export function ChatbotsPage() {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const system = useWorkspaceSystem();
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
  const [busy, setBusy] = useState<"create" | "save" | "delete">();
  const [pageFeedback, setPageFeedback] = useState<UiFeedback>();
  const [dirty, setDirty] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [mobileTab, setMobileTab] = useState<"config" | "chat">("chat");
  const [activeView, setActiveView] = useState<"workbench" | "web" | "facebook" | "zalo">(
    searchParams.get("channel") === "zalo" ? "zalo" : "workbench",
  );
  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";
  const selectedAgent = agents.find((item) => item.public_id === selectedId);
  const selectedDraft = draftAgentId === selectedAgent?.public_id ? draft : undefined;

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
          fallback: "Không thể tải cấu hình Agent. Vui lòng thử lại.",
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
          fallback: "Không thể tải nguồn kiến thức của Agent.",
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

  function openChannel(channel: "web" | "facebook" | "zalo") {
    if (dirty && !window.confirm(
      "Bỏ thay đổi cấu hình Agent chưa lưu để mở kênh?",
    )) return;
    if (dirty && selectedAgent) {
      setDraft(draftFrom(selectedAgent, draft?.knowledgeBaseIds));
      setDirty(false);
    }
    setActiveView(channel);
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
      await system?.loadOverview();
      setPageFeedback(feedback("success", "Đã tạo Agent. Bạn có thể cấu hình và thử ngay bây giờ."));
    } catch (caught) {
      setPageFeedback(toUiError(caught, {
        operation: "agents.create",
        fallback: "Không thể tạo Agent. Tên bạn đã nhập vẫn được giữ lại.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selectedAgent || !draft || !dirty) return;
    if (draft.intakeActionEnabled) {
      const hasReachableContact = draft.intakeDefinition.fields.some(
        (field) => field.semantic === "email" || field.semantic === "phone",
      );
      const invalidChoice = draft.intakeDefinition.fields.some(
        (field) => (field.kind === "single_choice" || field.kind === "multiple_choice")
          && field.options.length < 2,
      );
      if (!hasReachableContact || invalidChoice) {
        setPageFeedback(feedback(
          "error",
          !hasReachableContact
            ? "Cần ít nhất một mục email hoặc số điện thoại để có thể liên hệ khách Website."
            : "Mỗi mục lựa chọn cần ít nhất hai phương án.",
        ));
        return;
      }
    }
    setBusy("save");
    setSavedNotice(false);
    setPageFeedback(undefined);
    let completedWrites = 0;
    try {
      await api.updateAgent(workspace.id, selectedAgent.public_id, {
        name: draft.name,
        icon: draft.icon,
        color: draft.color,
        greeting: draft.greeting || null,
        safe_instructions: draft.safeInstructions || null,
        default_locale: draft.defaultLocale,
        follow_up_action_enabled: draft.followUpActionEnabled,
        intake_action_enabled: draft.intakeActionEnabled,
        intake_definition: draft.intakeDefinition,
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
        await Promise.all([
          loadAgents(workspace.id, selectedAgent.public_id),
          system?.loadOverview() ?? Promise.resolve(),
        ]);
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
        fallback: "Không thể lưu cấu hình Agent. Vui lòng thử lại.",
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

  async function deleteAgent() {
    if (!workspace || !selectedAgent) return;
    if (!window.confirm(
      `Xóa Agent "${selectedAgent.name}"? Agent sẽ ngừng hoạt động trên các kênh đang kết nối.`,
    )) return;

    setBusy("delete");
    setPageFeedback(undefined);
    try {
      await api.deleteAgent(workspace.id, selectedAgent.public_id);
      const remainingAgents = agents.filter(
        (item) => item.public_id !== selectedAgent.public_id,
      );
      const nextAgentId = remainingAgents[0]?.public_id;
      setAgents(remainingAgents);
      setSelectedId(nextAgentId);
      setDraft(undefined);
      setDraftAgentId(undefined);
      setDirty(false);
      setSavedNotice(false);
      setActiveView("workbench");
      const path = `/app/${encodeURIComponent(params.workspaceSlug)}/chatbots`;
      router.replace(
        nextAgentId ? `${path}?agent=${encodeURIComponent(nextAgentId)}` : path,
        { scroll: false },
      );
      await system?.loadOverview();
      setPageFeedback(feedback("success", "Đã xóa Agent."));
    } catch (caught) {
      setPageFeedback(toUiError(caught, {
        operation: "agents.delete",
        fallback: "Không thể xóa Agent. Vui lòng thử lại.",
      }));
    } finally {
      setBusy(undefined);
    }
  }

  function toggleId(field: "locationIds" | "collectionIds" | "knowledgeBaseIds", id: number) {
    if (!draft) return;
    const values = draft[field];
    updateDraft({ [field]: values.includes(id) ? values.filter((item) => item !== id) : [...values, id] });
  }

  function updateIntakeDefinition(update: Partial<IntakeDefinition>) {
    if (!draft) return;
    updateDraft({ intakeDefinition: { ...draft.intakeDefinition, ...update } });
  }

  function updateIntakeField(index: number, update: Partial<IntakeField>) {
    if (!draft) return;
    updateIntakeDefinition({
      fields: draft.intakeDefinition.fields.map((field, fieldIndex) =>
        fieldIndex === index ? { ...field, ...update } : field
      ),
    });
  }

  function moveIntakeField(index: number, offset: -1 | 1) {
    if (!draft) return;
    const fields = [...draft.intakeDefinition.fields];
    const nextIndex = index + offset;
    if (nextIndex < 0 || nextIndex >= fields.length) return;
    [fields[index], fields[nextIndex]] = [fields[nextIndex], fields[index]];
    updateIntakeDefinition({ fields });
  }

  if (workspaceError) return <main className="center-state"><FeedbackBanner feedback={workspaceError} onRetry={() => location.reload()} /></main>;
  if (!me || !workspace) return <main className="center-state" aria-live="polite">Đang tải workspace…</main>;

  return (
    <>
      <section className="page-heading chatbot-page-heading">
        <h1>Agents</h1>
        <div className="chatbot-heading-actions">
          {!canWrite && <span className="status-pill archived">Chỉ đọc</span>}
          {canWrite && <button className="secondary-button" onClick={() => setShowCreate((current) => !current)} type="button">{showCreate ? <X size={16} /> : <Plus size={16} />}{showCreate ? "Đóng" : "Tạo Agent"}</button>}
        </div>
      </section>
      {showCreate && canWrite && <form className="chatbot-create-bar" onSubmit={createAgent}><label><span>Tên Agent mới</span><input maxLength={160} name="name" placeholder="Ví dụ: Agent hỗ trợ" required /></label><button className="primary-button compact-button" disabled={busy === "create"} type="submit">{busy === "create" ? <LoaderCircle className="spinner" size={16} /> : <Plus size={16} />} Tạo Agent</button></form>}
      {pageFeedback && <FeedbackBanner feedback={pageFeedback} />}
      {savedNotice && <p className="success-message" role="status">Đã lưu cấu hình Agent.</p>}
      {loading && <section className="chatbot-page-state"><LoaderCircle className="spinner" size={20} /> Đang tải cấu hình…</section>}
      {!loading && agents.length === 0 && <section className="chatbot-page-state"><Bot size={30} /><h2>Chưa có Agent</h2><p>Tạo Agent đầu tiên để cấu hình kiến thức, phạm vi và thử phản hồi.</p>{canWrite && <button className="primary-button compact-button" onClick={() => setShowCreate(true)} type="button"><Plus size={16} /> Tạo Agent đầu tiên</button>}</section>}
      {!loading && selectedAgent && (
        <>
          <section className="chatbot-agent-strip">
            <span
              className="agent-avatar"
              style={{
                backgroundColor: selectedDraft?.color ?? selectedAgent.color,
                color: AGENT_GLYPH_COLOR,
              }}
            >
              <AgentGlyph icon={selectedDraft?.icon ?? selectedAgent.icon} size={19} />
            </span>
            <div className="chatbot-agent-copy"><strong>{selectedAgent.name}</strong><small>{selectedAgent.status === "published" ? "Đã phát hành" : selectedAgent.status === "paused" ? "Đã tạm dừng" : "Bản nháp"} · {draft?.knowledgeBaseIds.length ?? 0} nguồn tri thức · Catalog dùng khi có dữ liệu phù hợp</small></div>
            <div className="chatbot-agent-actions">
              {dirty && <span className="status-pill pending">Có thay đổi chưa lưu</span>}
              <div className="chatbot-view-switch" aria-label="Khu vực Agent" role="group"><button aria-pressed={activeView === "workbench"} onClick={() => setActiveView("workbench")} type="button"><Bot size={15} /> Cấu hình & thử</button><button aria-pressed={activeView === "web"} onClick={() => openChannel("web")} type="button"><Globe2 size={15} /> Kênh Web</button><button aria-pressed={activeView === "facebook"} onClick={() => openChannel("facebook")} type="button"><MessagesSquare size={15} /> Facebook</button><button aria-pressed={activeView === "zalo"} onClick={() => openChannel("zalo")} type="button"><MessageSquareText size={15} /> Zalo</button></div>
              <label className="chatbot-agent-select"><span className="sr-only">Đổi Agent</span><select aria-label="Đổi Agent" onChange={(event) => selectAgent(event.target.value)} value={selectedId}>{agents.map((agent) => <option key={agent.public_id} value={agent.public_id}>{agent.name}</option>)}</select></label>
              {canWrite && <button className="danger-button compact-button" disabled={Boolean(busy)} onClick={() => void deleteAgent()} type="button"><Trash2 size={16} /> Xóa Agent</button>}
            </div>
          </section>
          {activeView === "workbench" && <><div className="chatbot-mobile-tabs" role="tablist">
            <button aria-selected={mobileTab === "config"} onClick={() => setMobileTab("config")} role="tab" type="button">Cấu hình</button>
            <button aria-selected={mobileTab === "chat"} onClick={() => setMobileTab("chat")} role="tab" type="button">Thử Agent</button>
          </div>
          <div className="chatbot-workbench">
            <section className={`agent-config-card chatbot-config-panel ${mobileTab === "config" ? "mobile-active" : ""}`}>
              {!draft || draftAgentId !== selectedAgent.public_id ? <p className="compact-empty"><LoaderCircle className="spinner" size={18} /> Đang tải cấu hình…</p> : (
                <form onSubmit={saveAgent}>
                  <div className="card-heading agent-config-heading"><div><h2>Cấu hình</h2><p>Thay đổi áp dụng cho bản nháp sau khi lưu</p></div>{dirty && <span className="status-pill pending">Chưa lưu</span>}</div>
                  <div className="agent-config-sections">
                    <fieldset className="agent-fieldset" disabled={!canWrite}>
                      <legend>Danh tính và hành vi</legend>
                      <label>Tên<input maxLength={160} onChange={(event) => updateDraft({ name: event.target.value })} required value={draft.name} /></label>
                      <label>Ngôn ngữ<select onChange={(event) => updateDraft({ defaultLocale: event.target.value })} value={draft.defaultLocale}><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label>
                      <div className="agent-appearance-field full-field">
                        <span className="agent-appearance-label">Biểu tượng và màu sắc</span>
                        <div aria-label="Chọn biểu tượng Agent" className="agent-icon-options" role="group">
                          {AGENT_ICON_OPTIONS.map((option) => <button
                            aria-label={option.label}
                            aria-pressed={draft.icon === option.key}
                            key={option.key}
                            onClick={() => updateDraft({ icon: option.key })}
                            title={option.label}
                            type="button"
                          ><AgentGlyph icon={option.key} size={18} /></button>)}
                        </div>
                        <label className="agent-color-field">
                          <span>Màu lõi Agent</span>
                          <span className="agent-color-control">
                            <input aria-label="Màu lõi Agent" onChange={(event) => updateDraft({ color: event.target.value.toUpperCase() })} type="color" value={draft.color} />
                            <code>{draft.color}</code>
                            <i aria-hidden="true" style={{ backgroundColor: draft.color, color: AGENT_GLYPH_COLOR }}><AgentGlyph icon={draft.icon} size={20} /></i>
                          </span>
                        </label>
                      </div>
                      <label className="full-field">Lời chào<textarea maxLength={2000} onChange={(event) => updateDraft({ greeting: event.target.value })} rows={3} value={draft.greeting} /></label>
                      <label className="full-field">Tính cách và phong cách trả lời<small className="agent-field-help">Agent mới đã có cấu hình thân thiện để dùng ngay. Bạn có thể chỉnh cách xưng hô, độ dài và phong cách hỗ trợ tại đây.</small><textarea maxLength={10000} onChange={(event) => updateDraft({ safeInstructions: event.target.value })} placeholder="Ví dụ: Xưng hô gần gũi, trả lời ngắn gọn và luôn hỏi thêm nhu cầu của người dùng." rows={5} value={draft.safeInstructions} /></label>
                    </fieldset>
                    <fieldset className="agent-fieldset" disabled={!canWrite}>
                      <legend><PhoneForwarded aria-hidden="true" size={17} /> Yêu cầu liên hệ lại</legend>
                      <label className="check-option">
                        <input checked={draft.followUpActionEnabled} onChange={(event) => updateDraft({ followUpActionEnabled: event.target.checked })} type="checkbox" />
                        <span><strong>Cho phép Agent ghi nhận yêu cầu liên hệ</strong><small>Chỉ chạy trong hội thoại Website, Facebook hoặc Zalo đã xuất bản khi khách yêu cầu rõ ràng. Bật cần xuất bản revision mới; tắt sẽ chặn thực thi ngay sau khi lưu. Playground không tạo Lead.</small></span>
                      </label>
                    </fieldset>
                    <fieldset className="agent-fieldset" disabled={!canWrite}>
                      <legend><MessageSquareText aria-hidden="true" size={17} /> Thu thập thông tin qua hội thoại</legend>
                      <label className="check-option full-field">
                        <input
                          checked={draft.intakeActionEnabled}
                          onChange={(event) => updateDraft({ intakeActionEnabled: event.target.checked })}
                          type="checkbox"
                        />
                        <span>
                          <strong>Cho phép Agent ghi nhận thông tin có cấu trúc</strong>
                          <small>Agent vẫn trò chuyện tự nhiên như nhân viên: tự hiểu câu trả lời tự do, điền nhiều mục từ một tin nhắn và chỉ hỏi phần còn thiếu hoặc chưa rõ. Khách không phải điền biểu mẫu hay trả lời theo cú pháp. Playground không tạo Lead.</small>
                        </span>
                      </label>
                      {draft.intakeActionEnabled && <div className="intake-config full-field">
                        <label>Mục đích sử dụng
                          <input
                            maxLength={240}
                            onChange={(event) => updateIntakeDefinition({ purpose: event.target.value })}
                            required
                            value={draft.intakeDefinition.purpose}
                          />
                        </label>
                        <label>Lời giải thích với khách
                          <textarea
                            maxLength={500}
                            onChange={(event) => updateIntakeDefinition({ disclosure: event.target.value })}
                            required
                            rows={2}
                            value={draft.intakeDefinition.disclosure}
                          />
                        </label>
                        <p className="fieldset-help">Không thu thập mật khẩu, OTP, dữ liệu thanh toán, giấy tờ định danh, sinh trắc học hoặc hồ sơ sức khỏe.</p>
                        <div className="intake-field-list">
                          {draft.intakeDefinition.fields.map((field, index) => <div className="intake-field-row" key={field.key ?? `${field.semantic}-${index}`}>
                            <div className="intake-field-controls">
                              <label>Loại thông tin
                                <select
                                  onChange={(event) => updateIntakeField(index, fieldFor(event.target.value as IntakeFieldSemantic))}
                                  value={field.semantic}
                                >
                                  {intakeSemantics.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                                </select>
                              </label>
                              <label>Nhãn nội bộ
                                <input maxLength={80} onChange={(event) => updateIntakeField(index, { label: event.target.value })} required value={field.label} />
                              </label>
                              <label className="check-option compact-check">
                                <input checked={field.required} onChange={(event) => updateIntakeField(index, { required: event.target.checked })} type="checkbox" />
                                <span>Bắt buộc</span>
                              </label>
                            </div>
                            {(field.kind === "single_choice" || field.kind === "multiple_choice") && <label>Lựa chọn, phân cách bằng dấu phẩy
                              <input
                                onChange={(event) => updateIntakeField(index, {
                                  options: event.target.value.split(",").map((label, optionIndex) => ({
                                    key: field.options[optionIndex]?.key ?? null,
                                    label: label.trim(),
                                  })).filter((option) => option.label),
                                })}
                                value={field.options.map((option) => option.label).join(", ")}
                              />
                            </label>}
                            <div className="intake-field-actions">
                              <button aria-label={`Đưa ${field.label} lên`} className="icon-button" disabled={index === 0} onClick={() => moveIntakeField(index, -1)} type="button"><ChevronUp size={15} /></button>
                              <button aria-label={`Đưa ${field.label} xuống`} className="icon-button" disabled={index === draft.intakeDefinition.fields.length - 1} onClick={() => moveIntakeField(index, 1)} type="button"><ChevronDown size={15} /></button>
                              <button aria-label={`Xóa ${field.label}`} className="icon-button danger-icon" disabled={draft.intakeDefinition.fields.length === 1} onClick={() => updateIntakeDefinition({ fields: draft.intakeDefinition.fields.filter((_, fieldIndex) => fieldIndex !== index) })} type="button"><Trash2 size={15} /></button>
                            </div>
                          </div>)}
                        </div>
                        <button
                          className="secondary-button compact-button"
                          disabled={draft.intakeDefinition.fields.length >= 12}
                          onClick={() => updateIntakeDefinition({ fields: [...draft.intakeDefinition.fields, fieldFor("context")] })}
                          type="button"
                        ><Plus size={15} /> Thêm thông tin cần hỏi</button>
                      </div>}
                    </fieldset>
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
          {activeView === "facebook" && <FacebookChannelPanel canWrite={canWrite} key={selectedAgent.public_id} publicAgentId={selectedAgent.public_id} workspaceId={workspace.id} />}
          {activeView === "zalo" && <ZaloChannelPanel canWrite={canWrite} key={selectedAgent.public_id} publicAgentId={selectedAgent.public_id} workspaceId={workspace.id} />}
        </>
      )}
    </>
  );
}
