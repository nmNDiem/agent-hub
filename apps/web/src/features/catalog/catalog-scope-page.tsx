"use client";

import { Archive, Layers3, MapPin, Plus, Save } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  api,
  ApiError,
  type CatalogCollection,
  type Location,
  type LocationVariant,
  type Me,
  type ProductSummary,
  type Workspace,
} from "@/lib/api";

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể hoàn tất yêu cầu.";
}

function value(form: FormData, key: string): string {
  return String(form.get(key) ?? "").trim();
}

export function CatalogScopePage({ view }: { view: "locations" | "collections" }) {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const [me, setMe] = useState<Me>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [locations, setLocations] = useState<Location[]>([]);
  const [collections, setCollections] = useState<CatalogCollection[]>([]);
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<Location>();
  const [variants, setVariants] = useState<LocationVariant[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";

  useEffect(() => {
    let active = true;
    api.getMe().then(async (profile) => {
      const current = profile.workspaces.find((item) => item.slug === params.workspaceSlug);
      if (!current) throw new ApiError(404, "NOT_FOUND", "Không tìm thấy workspace.");
      const [locationItems, collectionItems, productPage] = await Promise.all([
        api.listLocations(current.id),
        api.listCollections(current.id),
        api.listProducts(current.id, { status: "active" }),
      ]);
      if (!active) return;
      setMe(profile);
      setWorkspace(current);
      setLocations(locationItems);
      setCollections(collectionItems);
      setProducts(productPage.items);
      if (view === "locations" && locationItems[0]) {
        setSelectedLocation(locationItems[0]);
        setVariants(await api.listLocationVariants(current.id, locationItems[0].id));
      }
    }).catch((caught: unknown) => {
      if (!active) return;
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
      } else setError(message(caught));
    });
    return () => { active = false; };
  }, [params.workspaceSlug, router, view]);

  async function reload() {
    if (!workspace) return;
    const [locationItems, collectionItems, productPage] = await Promise.all([
      api.listLocations(workspace.id),
      api.listCollections(workspace.id),
      api.listProducts(workspace.id, { status: "active" }),
    ]);
    setLocations(locationItems);
    setCollections(collectionItems);
    setProducts(productPage.items);
    if (selectedLocation) {
      setVariants(await api.listLocationVariants(workspace.id, selectedLocation.id));
    }
  }

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(undefined);
    try { await action(); await reload(); } catch (caught) { setError(message(caught)); }
    finally { setBusy(false); }
  }

  async function chooseLocation(locationItem: Location) {
    if (!workspace) return;
    setSelectedLocation(locationItem);
    setBusy(true);
    try { setVariants(await api.listLocationVariants(workspace.id, locationItem.id)); }
    catch (caught) { setError(message(caught)); }
    finally { setBusy(false); }
  }

  function createLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const form = new FormData(event.currentTarget);
    void run(() => api.createLocation(workspace.id, {
      name: value(form, "name"), code: value(form, "code") || null, type: value(form, "type"),
    }));
    event.currentTarget.reset();
  }

  function updateVariant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selectedLocation) return;
    const form = new FormData(event.currentTarget);
    const variantId = Number(value(form, "variant_id"));
    const quantity = value(form, "quantity");
    const price = value(form, "price_override");
    void run(() => api.updateLocationVariant(workspace.id, selectedLocation.id, variantId, {
      is_active: form.get("is_active") === "on",
      quantity: quantity === "" ? null : Number(quantity),
      price_override: price || null,
    }));
  }

  function createCollection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const form = new FormData(event.currentTarget);
    void run(() => api.createCollection(workspace.id, {
      name: value(form, "name"), description: value(form, "description") || null,
    }));
    event.currentTarget.reset();
  }

  if (!me || !workspace) {
    return <main className="center-state"><p role="alert">{error ?? "Đang tải catalog scope…"}</p></main>;
  }

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <header className="page-heading catalog-heading">
        <div><p className="eyebrow">Workspace catalog</p><h1>{view === "locations" ? "Locations" : "Collections"}</h1>
          <p>{view === "locations" ? "Quản lý nơi bán, tồn kho và giá override theo variant." : "Tổ chức master catalog thành các nhóm tái sử dụng."}</p></div>
      </header>
      {error && <p className="form-error" role="alert">{error}</p>}
      {view === "locations" ? (
        <div className="scope-layout">
          <section className="catalog-list-card">
            <div className="card-heading"><div><h2>Locations</h2><p>Domain generic cho cửa hàng, kho và điểm dịch vụ.</p></div><MapPin /></div>
            <div className="scope-list">{locations.map((item) => (
              <button className={selectedLocation?.id === item.id ? "scope-item active" : "scope-item"} key={item.id} onClick={() => void chooseLocation(item)} type="button">
                <span><strong>{item.name}</strong><small>{item.code ?? "Không có code"} · {item.type}</small></span><span className="status-pill active">Đang hoạt động</span>
              </button>
            ))}</div>
            {canWrite && <form className="catalog-form" onSubmit={createLocation}>
              <h3>Thêm location</h3><label>Tên<input name="name" required /></label>
              <div className="form-columns"><label>Code<input name="code" pattern="[A-Za-z0-9_-]+" /></label><label>Loại<select name="type"><option value="store">Store</option><option value="warehouse">Warehouse</option><option value="showroom">Showroom</option><option value="online">Online</option><option value="other">Other</option></select></label></div>
              <button className="primary-button" disabled={busy} type="submit"><Plus size={16} /> Tạo location</button>
            </form>}
          </section>
          <section className="catalog-list-card">
            <div className="card-heading"><div><h2>{selectedLocation?.name ?? "Chọn location"}</h2><p>Chỉ variant được activate tại location mới xuất hiện trong scoped search.</p></div>{selectedLocation && canWrite && <button aria-label="Archive location" className="icon-button" onClick={() => void run(() => api.archiveLocation(workspace.id, selectedLocation.id))} type="button"><Archive size={16} /></button>}</div>
            {variants.length === 0 ? <div className="catalog-empty"><MapPin /><h3>Chưa có variant</h3><p>Nhập variant ID bên dưới để activate tại location này.</p></div> : <div className="location-variant-list">{variants.map((item) => <article key={item.variant_id}><div><strong>{item.product_name}</strong><small>{item.variant_sku ?? `Variant #${item.variant_id}`}</small></div><div><strong>{item.quantity === null ? "Chưa biết tồn kho" : `Tồn kho: ${item.quantity}`}</strong><small>Giá: {item.effective_price ?? "Chưa có"}</small></div></article>)}</div>}
            {canWrite && selectedLocation && <form className="catalog-form" onSubmit={updateVariant}>
              <h3>Activate / cập nhật variant</h3><div className="form-columns"><label>Variant ID<input min="1" name="variant_id" required type="number" /></label><label>Tồn kho<input min="0" name="quantity" type="number" /></label></div>
              <label>Giá override<input inputMode="decimal" name="price_override" /></label><label className="checkbox-field"><input defaultChecked name="is_active" type="checkbox" /> Đang bán tại location</label>
              <button className="primary-button" disabled={busy} type="submit"><Save size={16} /> Lưu</button>
            </form>}
          </section>
        </div>
      ) : (
        <div className="scope-layout">
          <section className="catalog-list-card"><div className="card-heading"><div><h2>Collections</h2><p>Một product có thể thuộc nhiều collections.</p></div><Layers3 /></div>
            <div className="collection-grid">{collections.map((collection) => <article key={collection.id}><div><strong>{collection.name}</strong><small>{collection.description ?? "Không có mô tả"}</small></div><p>{collection.product_ids.length} sản phẩm</p><div className="collection-products">{collection.product_ids.map((id) => <button className="status-pill archived" key={id} onClick={() => void run(() => api.removeCollectionProduct(workspace.id, collection.id, id))} type="button">#{id} ×</button>)}</div>{canWrite && <div className="form-actions"><select aria-label={`Thêm sản phẩm vào ${collection.name}`} defaultValue="" id={`product-${collection.id}`}>{<option disabled value="">Chọn sản phẩm</option>}{products.filter((product) => !collection.product_ids.includes(product.id)).map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select><button className="secondary-button" onClick={() => { const element = document.getElementById(`product-${collection.id}`) as HTMLSelectElement | null; if (element?.value) void run(() => api.addCollectionProduct(workspace.id, collection.id, Number(element.value))); }} type="button"><Plus size={15} /> Thêm</button><button className="icon-button" aria-label={`Archive ${collection.name}`} onClick={() => void run(() => api.archiveCollection(workspace.id, collection.id))} type="button"><Archive size={15} /></button></div>}</article>)}</div>
          </section>
          {canWrite && <section className="catalog-list-card"><div className="card-heading"><div><h2>Tạo collection</h2><p>Nhóm products mà không duplicate master catalog.</p></div></div><form className="catalog-form" onSubmit={createCollection}><label>Tên<input name="name" required /></label><label>Mô tả<textarea name="description" rows={4} /></label><button className="primary-button" disabled={busy} type="submit"><Plus size={16} /> Tạo collection</button></form></section>}
        </div>
      )}
    </AppShell>
  );
}
