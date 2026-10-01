"use client";

import { Bot, Boxes, LoaderCircle, MapPin, MessageSquareText, Plus, Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  api,
  ApiError,
  type Agent,
  type CatalogCollection,
  type KnowledgeBase,
  type Location,
} from "@/lib/api";
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

function messageFrom(error: unknown) {
  return error instanceof ApiError ? error.message : "Không thể hoàn tất thao tác. Vui lòng thử lại.";
}

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
  const { me, workspace, error: workspaceError } = useWorkspace(params.workspaceSlug);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [collections, setCollections] = useState<CatalogCollection[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [draft, setDraft] = useState<AgentDraft>();
  const [draftAgentId, setDraftAgentId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>();
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";
  const selectedAgent = agents.find((item) => item.public_id === selectedId);

  async function loadAgents(workspaceId: string) {
    const result = await api.listAgents(workspaceId);
    setAgents(result.items);
    if (result.items.length === 0) {
      setDraft(undefined);
      setDraftAgentId(undefined);
    }
    setSelectedId((current) =>
      current && result.items.some((item) => item.public_id === current)
        ? current
        : result.items[0]?.public_id,
    );
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
      setAgents(agentResult.items);
      setSelectedId(agentResult.items[0]?.public_id);
      setKnowledgeBases(bases.items);
      setLocations(locationItems.filter((item) => item.is_active));
      setCollections(collectionItems.filter((item) => item.is_active));
    }).catch((caught) => {
      if (active) setError(messageFrom(caught));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [workspace]);

  useEffect(() => {
    if (!workspace || !selectedAgent) return;
    let active = true;
    api.getAgentKnowledgeBases(workspace.id, selectedAgent.public_id).then((result) => {
      if (active) {
        setDraft(draftFrom(selectedAgent, result.knowledge_base_ids));
        setDraftAgentId(selectedAgent.public_id);
      }
    }).catch((caught) => {
      if (active) setError(messageFrom(caught));
    });
    return () => { active = false; };
  }, [selectedAgent, workspace]);

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const form = new FormData(event.currentTarget);
    setBusy("create");
    setError(undefined);
    try {
      const created = await api.createAgent(workspace.id, {
        name: String(form.get("name")),
        default_locale: "vi",
      });
      event.currentTarget.reset();
      await loadAgents(workspace.id);
      setSelectedId(created.public_id);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(undefined);
    }
  }

  async function saveAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selectedAgent || !draft) return;
    setBusy("save");
    setSaved(false);
    setError(undefined);
    try {
      await api.updateAgent(workspace.id, selectedAgent.public_id, {
        name: draft.name,
        greeting: draft.greeting || null,
        safe_instructions: draft.safeInstructions || null,
        default_locale: draft.defaultLocale,
      });
      await api.replaceAgentCatalogScope(workspace.id, selectedAgent.public_id, {
        location_ids: draft.allLocations ? null : draft.locationIds,
        collection_ids: draft.allCollections ? null : draft.collectionIds,
      });
      await api.replaceAgentKnowledgeBases(
        workspace.id,
        selectedAgent.public_id,
        draft.knowledgeBaseIds,
      );
      await loadAgents(workspace.id);
      setSaved(true);
    } catch (caught) {
      setError(messageFrom(caught));
    } finally {
      setBusy(undefined);
    }
  }

  function toggleId(field: "locationIds" | "collectionIds" | "knowledgeBaseIds", id: number) {
    setSaved(false);
    setDraft((current) => {
      if (!current) return current;
      const values = current[field];
      return { ...current, [field]: values.includes(id) ? values.filter((item) => item !== id) : [...values, id] };
    });
  }

  if (workspaceError) return <main className="center-state"><p role="alert">{workspaceError}</p></main>;
  if (!me || !workspace) return <main className="center-state" aria-live="polite">Đang tải cửa hàng…</main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="page-heading catalog-heading">
        <div><p className="eyebrow">Trợ lý AI</p><h1>Chatbot</h1><p>Cấu hình bản nháp và kiểm thử trên dữ liệu thật trước khi xuất bản.</p></div>
        {!canWrite && <span className="status-pill archived">Chỉ đọc</span>}
      </section>
      {error && <p className="form-error" role="alert">{error}</p>}
      {saved && <p className="success-message" role="status">Đã lưu cấu hình chatbot.</p>}
      <div className="agents-layout">
        <aside className="agent-list-card">
          <div className="card-heading"><div><h2>Chatbot</h2><p>{agents.length} bản cấu hình</p></div><Bot aria-hidden="true" /></div>
          {canWrite && <form className="agent-create-form" onSubmit={createAgent}><input aria-label="Tên chatbot mới" name="name" placeholder="Tên chatbot" required /><button aria-label="Tạo chatbot" className="icon-button" disabled={busy === "create"} type="submit">{busy === "create" ? <LoaderCircle className="spinner" size={16} /> : <Plus size={16} />}</button></form>}
          <div className="agent-list" role="listbox" aria-label="Danh sách chatbot">
            {agents.map((agent) => <button aria-selected={agent.public_id === selectedId} className="agent-list-item" key={agent.public_id} onClick={() => setSelectedId(agent.public_id)} role="option" type="button"><span className="agent-avatar" aria-hidden="true"><Bot size={17} /></span><span><strong>{agent.name}</strong><small>{agent.status === "draft" ? "Bản nháp" : agent.status}</small></span></button>)}
            {!loading && agents.length === 0 && <p className="compact-empty">Chưa có chatbot. Tạo chatbot đầu tiên để bắt đầu.</p>}
          </div>
        </aside>
        <section className="agent-config-card">
          {loading && <p className="compact-empty"><LoaderCircle className="spinner" size={18} /> Đang tải cấu hình…</p>}
          {!loading && !selectedAgent && <p className="compact-empty"><MessageSquareText size={24} /> Chọn hoặc tạo chatbot để cấu hình.</p>}
          {selectedAgent && draft && draftAgentId === selectedAgent.public_id && (
            <form onSubmit={saveAgent}>
              <div className="card-heading agent-config-heading"><div><h2>{selectedAgent.name}</h2><p>Đang chỉnh sửa bản nháp · model do máy chủ quản lý</p></div><Link className="secondary-button" href={`/app/${workspace.slug}/chatbots/${selectedAgent.public_id}/playground`}>Mở Playground</Link></div>
              <div className="agent-config-sections">
                <fieldset className="agent-fieldset" disabled={!canWrite}><legend>Thông tin và hành vi</legend><label>Tên<input maxLength={160} onChange={(event) => { setSaved(false); setDraft({ ...draft, name: event.target.value }); }} required value={draft.name} /></label><label>Ngôn ngữ<select onChange={(event) => { setSaved(false); setDraft({ ...draft, defaultLocale: event.target.value }); }} value={draft.defaultLocale}><option value="vi">Tiếng Việt</option><option value="en">English</option></select></label><label className="full-field">Lời chào<textarea maxLength={2000} onChange={(event) => { setSaved(false); setDraft({ ...draft, greeting: event.target.value }); }} rows={3} value={draft.greeting} /></label><label className="full-field">Giọng điệu và hướng dẫn an toàn<textarea maxLength={10000} onChange={(event) => { setSaved(false); setDraft({ ...draft, safeInstructions: event.target.value }); }} placeholder="Ví dụ: Trả lời ngắn gọn, thân thiện; không suy đoán thông tin ngoài dữ liệu." rows={5} value={draft.safeInstructions} /></label></fieldset>
                <fieldset className="agent-fieldset" disabled={!canWrite}><legend><BookIcon /> Nguồn tri thức</legend><p className="fieldset-help">Chỉ dữ liệu đã ingestion thành công mới có thể được runtime truy xuất.</p><div className="scope-options">{knowledgeBases.map((base) => <label className="check-option" key={base.id}><input checked={draft.knowledgeBaseIds.includes(base.id)} onChange={() => toggleId("knowledgeBaseIds", base.id)} type="checkbox" /><span><strong>{base.name}</strong><small>{base.document_count} tài liệu · {base.kind}</small></span></label>)}{knowledgeBases.length === 0 && <p className="muted-copy">Chưa có kho tri thức.</p>}</div></fieldset>
                <fieldset className="agent-fieldset" disabled={!canWrite}><legend><MapPin size={17} /> Phạm vi location</legend><label className="check-option"><input checked={draft.allLocations} onChange={(event) => setDraft({ ...draft, allLocations: event.target.checked })} type="checkbox" /><span><strong>Tất cả location đang hoạt động</strong><small>Tự động bao gồm location mới.</small></span></label>{!draft.allLocations && <div className="scope-options">{locations.map((location) => <label className="check-option" key={location.id}><input checked={draft.locationIds.includes(location.id)} onChange={() => toggleId("locationIds", location.id)} type="checkbox" /><span>{location.name}</span></label>)}</div>}</fieldset>
                <fieldset className="agent-fieldset" disabled={!canWrite}><legend><Boxes size={17} /> Phạm vi collection</legend><label className="check-option"><input checked={draft.allCollections} onChange={(event) => setDraft({ ...draft, allCollections: event.target.checked })} type="checkbox" /><span><strong>Tất cả collection đang hoạt động</strong><small>Tự động bao gồm collection mới.</small></span></label>{!draft.allCollections && <div className="scope-options">{collections.map((collection) => <label className="check-option" key={collection.id}><input checked={draft.collectionIds.includes(collection.id)} onChange={() => toggleId("collectionIds", collection.id)} type="checkbox" /><span>{collection.name}</span></label>)}</div>}</fieldset>
              </div>
              {canWrite && <div className="agent-save-bar"><span>{saved ? "Không có thay đổi chưa lưu" : "Các thay đổi chỉ áp dụng cho bản nháp"}</span><button className="primary-button compact-button" disabled={busy === "save"} type="submit">{busy === "save" ? <LoaderCircle className="spinner" size={16} /> : <Save size={16} />} Lưu cấu hình</button></div>}
            </form>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function BookIcon() {
  return <MessageSquareText aria-hidden="true" size={17} />;
}
