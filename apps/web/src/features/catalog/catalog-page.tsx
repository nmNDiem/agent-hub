"use client";

import {
  Archive,
  Boxes,
  ChevronRight,
  FileSpreadsheet,
  ImagePlus,
  LoaderCircle,
  Package,
  PackagePlus,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  api,
  ApiError,
  type Me,
  type ProductDetail,
  type ProductImage,
  type ProductSummary,
  type ProductVariant,
  type Workspace,
} from "@/lib/api";
import { CatalogImportWizard } from "./catalog-import-wizard";

type ActionPanel = "create" | "import";
type DetailTab = "overview" | "variants" | "images" | "guide";

const detailTabs: Array<{ id: DetailTab; label: string }> = [
  { id: "overview", label: "Tổng quan" },
  { id: "variants", label: "Biến thể" },
  { id: "images", label: "Hình ảnh" },
  { id: "guide", label: "Hướng dẫn" },
];

function text(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function nullable(form: FormData, name: string): string | null {
  return text(form, name) || null;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Không thể hoàn tất yêu cầu. Vui lòng thử lại.";
}

function formatPrice(value: string | null, currency: string): string {
  if (value === null) return "Chưa có giá";
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency }).format(Number(value));
}

function formatUpdated(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short" }).format(new Date(value));
}

function variantOptions(variant: ProductVariant): string {
  const genericOptions = Object.values(variant.options ?? {}).filter(Boolean);
  const compatibilityOptions = [variant.color, variant.size].filter(
    (value): value is string => Boolean(value),
  );
  const values = genericOptions.length > 0 ? genericOptions : compatibilityOptions;
  return values.join(" · ") || "Không có lựa chọn";
}

function imageName(image: ProductImage): string {
  return image.original_filename ?? "Ảnh từ nguồn import";
}

export function CatalogPage() {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const [me, setMe] = useState<Me>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selected, setSelected] = useState<ProductDetail>();
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [actionPanel, setActionPanel] = useState<ActionPanel>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});

  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";
  const categories = useMemo(
    () => [...new Set([
      ...products.map((product) => product.category),
      categoryFilter || null,
    ].filter(Boolean))].sort(),
    [categoryFilter, products],
  ) as string[];
  const activeImages = selected?.images.filter((image) => image.status === "active") ?? [];
  const commonImageCount = activeImages.filter((image) => image.variant_id === null).length;
  const variantImageCount = activeImages.length - commonImageCount;

  useEffect(() => {
    let active = true;
    api.getMe().then(async (profile) => {
      if (!active) return;
      const current = profile.workspaces.find((item) => item.slug === params.workspaceSlug);
      if (!current) {
        setError("Không tìm thấy cửa hàng hoặc bạn không có quyền truy cập.");
        setLoading(false);
        return;
      }
      setMe(profile);
      setWorkspace(current);
      const result = await api.listProducts(current.id, { status: "active" });
      if (!active) return;
      setProducts(result.items);
      setNextCursor(result.next_cursor);
      setLoading(false);
    }).catch((caught: unknown) => {
      if (!active) return;
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
      } else {
        setError(errorMessage(caught));
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, [params.workspaceSlug, router]);

  useEffect(() => {
    let active = true;
    if (!workspace || !selected) return () => { active = false; };
    const images = selected.images.filter((image) => image.status === "active");
    Promise.all(images.map(async (image) => {
      try {
        const result = await api.getProductImageUrl(workspace.id, selected.id, image.id);
        return [image.id, result.url] as const;
      } catch {
        return null;
      }
    })).then((entries) => {
      if (!active) return;
      setImageUrls(Object.fromEntries(entries.filter((entry) => entry !== null)));
    });
    return () => { active = false; };
  }, [selected, workspace]);

  async function refreshProducts(cursor?: string, append = false) {
    if (!workspace) return;
    setBusy(true);
    setError(undefined);
    try {
      const result = await api.listProducts(workspace.id, {
        query: query || undefined,
        status: statusFilter || undefined,
        category: categoryFilter || undefined,
        cursor,
      });
      setProducts((current) => append ? [...current, ...result.items] : result.items);
      setNextCursor(result.next_cursor);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function openProduct(productId: number) {
    if (!workspace) return;
    setBusy(true);
    setError(undefined);
    setActiveTab("overview");
    setImageUrls({});
    try {
      setSelected(await api.getProduct(workspace.id, productId));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function mutate(action: () => Promise<unknown>, success: string, reloadDetail = true) {
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    try {
      await action();
      setNotice(success);
      await refreshProducts();
      if (reloadDetail && workspace && selected) {
        setSelected(await api.getProduct(workspace.id, selected.id));
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function createProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await mutate(async () => {
      const product = await api.createProduct(workspace.id, {
        product_sku: nullable(form, "product_sku"),
        name: text(form, "name"),
        category: nullable(form, "category"),
        currency: text(form, "currency") || "VND",
        price: nullable(form, "price"),
        product_url: nullable(form, "product_url"),
      });
      setSelected(product);
      setActiveTab("overview");
      setImageUrls({});
      setActionPanel(undefined);
      formElement.reset();
    }, "Đã tạo sản phẩm.", false);
  }

  async function updateProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selected) return;
    const form = new FormData(event.currentTarget);
    await mutate(async () => {
      setSelected(await api.updateProduct(workspace.id, selected.id, {
        product_sku: nullable(form, "product_sku"),
        name: text(form, "name"),
        description: nullable(form, "description"),
        category: nullable(form, "category"),
        currency: text(form, "currency"),
        price: nullable(form, "price"),
        product_url: nullable(form, "product_url"),
      }));
    }, "Đã cập nhật sản phẩm.", false);
  }

  async function addVariant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selected) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await mutate(async () => {
      await api.createVariant(workspace.id, selected.id, {
        variant_sku: nullable(form, "variant_sku"),
        name: nullable(form, "variant_name"),
        color: nullable(form, "color"),
        size: nullable(form, "size"),
        price_override: nullable(form, "price_override"),
        stock_quantity: nullable(form, "stock_quantity"),
      });
      formElement.reset();
    }, "Đã thêm biến thể.");
  }

  async function saveSizeGuide(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selected) return;
    const form = new FormData(event.currentTarget);
    let content: Record<string, unknown>;
    try {
      content = JSON.parse(text(form, "content")) as Record<string, unknown>;
    } catch {
      setError("Nội dung hướng dẫn phải là JSON hợp lệ.");
      return;
    }
    await mutate(
      () => api.putSizeGuide(workspace.id, selected.id, { title: text(form, "title"), content }),
      "Đã lưu hướng dẫn.",
    );
  }

  async function uploadImage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selected) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (!text(form, "variant_id")) form.delete("variant_id");
    await mutate(
      () => api.uploadProductImage(workspace.id, selected.id, form),
      "Đã tải ảnh lên kho riêng tư.",
    );
    formElement.reset();
  }

  function imageVariantLabel(image: ProductImage): string {
    if (image.variant_id === null) return "Ảnh chung";
    const variant = selected?.variants.find((item) => item.id === image.variant_id);
    return variant?.variant_sku ?? variant?.name ?? `Biến thể #${image.variant_id}`;
  }

  function renderImageThumbnail(image: ProductImage, compact = false) {
    const url = imageUrls[image.id];
    return url ? (
      <button
        aria-label={`Xem ${image.alt_text ?? imageName(image)}`}
        className={`image-thumbnail ${compact ? "compact" : ""}`}
        onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
        style={{ backgroundImage: `url(${url})` }}
        type="button"
      />
    ) : (
      <span className={`image-thumbnail image-placeholder ${compact ? "compact" : ""}`}>
        <ImagePlus aria-hidden="true" size={compact ? 15 : 19} />
      </span>
    );
  }

  if (loading) return <main className="center-state" aria-live="polite">Đang tải catalog…</main>;
  if (!me || !workspace) return <main className="center-state"><p role="alert">{error}</p></main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="page-heading catalog-heading">
        <div>
          <p className="eyebrow">Catalog / Sản phẩm</p>
          <h1>Danh mục sản phẩm</h1>
          <p>Quản lý sản phẩm, biến thể, giá và tồn kho tại một nơi.</p>
        </div>
        {canWrite && (
          <div className="catalog-heading-actions">
            <div>
              <button
                aria-expanded={actionPanel === "import"}
                className="secondary-button catalog-action-button"
                onClick={() => setActionPanel((current) => current === "import" ? undefined : "import")}
                type="button"
              >
                <FileSpreadsheet aria-hidden="true" size={18} /> Nhập từ file
              </button>
              <small>CSV, XLS, XLSX · Phân tích trước khi nhập</small>
            </div>
            <button
              aria-expanded={actionPanel === "create"}
              className="primary-button compact-button"
              onClick={() => setActionPanel((current) => current === "create" ? undefined : "create")}
              type="button"
            >
              <PackagePlus aria-hidden="true" size={18} /> Thêm sản phẩm
            </button>
          </div>
        )}
      </section>

      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="success-message" role="status">{notice}</p>}

      {canWrite && actionPanel && (
        <section className="catalog-action-surface" aria-label={actionPanel === "create" ? "Tạo sản phẩm" : "Nhập sản phẩm"}>
          <div className="catalog-action-surface-header">
            <div>
              <strong>{actionPanel === "create" ? "Tạo sản phẩm thủ công" : "Nhập catalog từ file"}</strong>
              <span>{actionPanel === "create" ? "Có thể bổ sung biến thể và hình ảnh sau khi tạo." : "Hệ thống phân tích và hiển thị thay đổi trước khi ghi dữ liệu."}</span>
            </div>
            <button aria-label="Đóng bảng thao tác" className="icon-button" onClick={() => setActionPanel(undefined)} type="button"><X size={18} /></button>
          </div>
          {actionPanel === "create" ? (
            <form className="catalog-form create-product-form" onSubmit={createProduct}>
              <label>Tên sản phẩm<input name="name" required maxLength={200} /></label>
              <label>Product SKU<input name="product_sku" maxLength={100} /></label>
              <label>Danh mục<input name="category" maxLength={120} /></label>
              <label>Giá<input name="price" inputMode="decimal" placeholder="Để trống nếu chưa biết" /></label>
              <label>Tiền tệ<input name="currency" defaultValue="VND" maxLength={3} required /></label>
              <label>URL sản phẩm<input name="product_url" type="url" /></label>
              <div className="form-actions">
                <button className="secondary-button" onClick={() => setActionPanel(undefined)} type="button">Hủy</button>
                <button className="primary-button compact-button" disabled={busy} type="submit">Tạo sản phẩm</button>
              </div>
            </form>
          ) : (
            <CatalogImportWizard workspaceId={workspace.id} onCommitted={() => refreshProducts()} />
          )}
        </section>
      )}

      <section className="catalog-toolbar" aria-label="Bộ lọc catalog">
        <form onSubmit={(event) => { event.preventDefault(); void refreshProducts(); }}>
          <label className="search-field">
            <Search size={18} aria-hidden="true" />
            <span className="sr-only">Tìm sản phẩm</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo tên hoặc SKU" />
          </label>
          <label>
            <span className="sr-only">Danh mục</span>
            <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="">Tất cả danh mục</option>
              {categories.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </label>
          <label>
            <span className="sr-only">Trạng thái</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="active">Đang bán</option>
              <option value="archived">Đã lưu trữ</option>
              <option value="">Tất cả trạng thái</option>
            </select>
          </label>
          <button className="secondary-button" disabled={busy} type="submit"><SlidersHorizontal aria-hidden="true" size={17} /> Áp dụng</button>
        </form>
        {busy && <LoaderCircle className="spinner" aria-label="Đang xử lý" size={20} />}
      </section>

      <div className={`catalog-workbench ${selected ? "has-detail" : ""}`}>
        <section className="catalog-list-card" aria-labelledby="catalog-list-title">
          <div className="card-heading catalog-list-heading">
            <div><h2 id="catalog-list-title">Sản phẩm</h2><p>{products.length} bản ghi đang hiển thị</p></div>
            <Boxes aria-hidden="true" />
          </div>
          {products.length === 0 ? (
            <div className="catalog-empty">
              <Boxes size={38} />
              <h3>Sản phẩm chưa có</h3>
              <p>Tạo thủ công hoặc nhập catalog từ CSV, XLS hoặc XLSX.</p>
              {canWrite && <div className="catalog-empty-actions"><button className="secondary-button" onClick={() => setActionPanel("import")} type="button">Nhập từ file</button><button className="primary-button compact-button" onClick={() => setActionPanel("create")} type="button">Thêm sản phẩm</button></div>}
            </div>
          ) : (
            <div className="product-table-wrap">
              <table className="product-table">
                <thead><tr><th>Sản phẩm</th><th>Danh mục</th><th>Biến thể</th><th>Giá</th><th>Trạng thái</th><th>Cập nhật</th><th><span className="sr-only">Thao tác</span></th></tr></thead>
                <tbody>
                  {products.map((product) => (
                    <tr className={selected?.id === product.id ? "is-selected" : undefined} key={product.id}>
                      <td>
                        <button className="product-identity" onClick={() => void openProduct(product.id)} type="button">
                          <span className="product-thumb"><Package aria-hidden="true" size={19} /></span>
                          <span><strong>{product.name}</strong><small>SKU: {product.product_sku ?? "Chưa có"}</small></span>
                        </button>
                      </td>
                      <td>{product.category ?? "Chưa phân loại"}</td>
                      <td>{product.variant_count}</td>
                      <td>{formatPrice(product.price, product.currency)}</td>
                      <td><i className={`status-pill ${product.status}`}>{product.status === "active" ? "Đang bán" : "Lưu trữ"}</i></td>
                      <td>{formatUpdated(product.updated_at)}</td>
                      <td><button aria-label={`Mở chi tiết ${product.name}`} className="icon-button row-action" onClick={() => void openProduct(product.id)} type="button"><ChevronRight size={18} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {nextCursor && <button className="load-more" disabled={busy} onClick={() => void refreshProducts(nextCursor, true)} type="button">Tải thêm sản phẩm</button>}
        </section>

        {selected && (
          <aside className="product-detail-panel" aria-labelledby="product-detail-title">
            <header className="product-detail-header">
              {activeImages[0] ? renderImageThumbnail(activeImages[0]) : <span className="detail-product-thumb"><Package aria-hidden="true" size={24} /></span>}
              <div><h2 id="product-detail-title">{selected.name}</h2><p>SKU: {selected.product_sku ?? "Chưa có"}</p><i className={`status-pill ${selected.status}`}>{selected.status === "active" ? "Đang bán" : "Lưu trữ"}</i></div>
              <button aria-label="Đóng chi tiết" className="icon-button" onClick={() => { setSelected(undefined); setImageUrls({}); }} type="button"><X size={19} /></button>
            </header>

            <div className="product-detail-tabs" role="tablist" aria-label="Chi tiết sản phẩm">
              {detailTabs.map((tab) => <button aria-controls={`product-panel-${tab.id}`} aria-selected={activeTab === tab.id} id={`product-tab-${tab.id}`} key={tab.id} onClick={() => setActiveTab(tab.id)} role="tab" type="button">{tab.label}</button>)}
            </div>

            <div className="product-detail-content">
              {activeTab === "overview" && (
                <section aria-labelledby="product-tab-overview" id="product-panel-overview" role="tabpanel">
                  <div className="detail-section-heading"><div><h3>Thông tin sản phẩm</h3><p>Dữ liệu cơ bản dùng cho quản lý và chatbot.</p></div></div>
                  {canWrite ? (
                    <form className="catalog-form product-fields" onSubmit={updateProduct}>
                      <div className="form-columns"><label>Tên<input defaultValue={selected.name} name="name" required /></label><label>Product SKU<input defaultValue={selected.product_sku ?? ""} name="product_sku" /></label></div>
                      <label>Mô tả<textarea defaultValue={selected.description ?? ""} name="description" rows={3} /></label>
                      <div className="form-columns"><label>Danh mục<input defaultValue={selected.category ?? ""} name="category" /></label><label>URL<input defaultValue={selected.product_url ?? ""} name="product_url" type="url" /></label></div>
                      <div className="form-columns"><label>Giá<input defaultValue={selected.price ?? ""} name="price" inputMode="decimal" /></label><label>Tiền tệ<input defaultValue={selected.currency} name="currency" required maxLength={3} /></label></div>
                      <div className="form-actions"><button className="primary-button compact-button" disabled={busy} type="submit">Lưu thay đổi</button>{selected.status === "active" && <button className="danger-button compact-danger" disabled={busy} onClick={() => { if (confirm("Lưu trữ sản phẩm này? SKU vẫn được giữ chỗ.")) void mutate(() => api.archiveProduct(workspace.id, selected.id), "Đã lưu trữ sản phẩm.", false).then(() => setSelected(undefined)); }} type="button"><Archive size={16} /> Lưu trữ</button>}</div>
                    </form>
                  ) : (
                    <dl className="product-facts"><div><dt>Danh mục</dt><dd>{selected.category ?? "Chưa phân loại"}</dd></div><div><dt>Giá</dt><dd>{formatPrice(selected.price, selected.currency)}</dd></div><div><dt>Mô tả</dt><dd>{selected.description ?? "Chưa có mô tả"}</dd></div><div><dt>URL</dt><dd>{selected.product_url ?? "Chưa có"}</dd></div></dl>
                  )}
                  <section className="compact-image-summary" aria-label="Tóm tắt hình ảnh">
                    <div className="compact-image-strip">{activeImages.slice(0, 3).map((image) => <span key={image.id}>{renderImageThumbnail(image, true)}</span>)}{activeImages.length === 0 && <span className="compact-image-empty"><ImagePlus aria-hidden="true" size={18} /></span>}</div>
                    <div><strong>{activeImages.length} hình ảnh</strong><p><span>{commonImageCount} ảnh chung</span><span>{variantImageCount} ảnh theo biến thể</span></p></div>
                    <button className="text-button" onClick={() => setActiveTab("images")} type="button">Quản lý ảnh</button>
                  </section>
                </section>
              )}

              {activeTab === "variants" && (
                <section aria-labelledby="product-tab-variants" id="product-panel-variants" role="tabpanel">
                  <div className="detail-section-heading"><div><h3>Danh sách biến thể ({selected.variants.length})</h3><p>Giá và tồn kho được giữ theo từng biến thể và location.</p></div></div>
                  {selected.variants.length === 0 ? <p className="detail-empty">Sản phẩm này chưa có biến thể.</p> : <div className="variant-table-wrap"><table className="variant-table"><thead><tr><th>SKU biến thể</th><th>Phân loại</th><th>Giá</th><th>Tồn kho</th><th><span className="sr-only">Thao tác</span></th></tr></thead><tbody>{selected.variants.map((variant) => <tr key={variant.id}><td><strong>{variant.variant_sku ?? variant.name ?? `#${variant.id}`}</strong></td><td>{variantOptions(variant)}</td><td>{formatPrice(variant.effective_price, selected.currency)}</td><td><div className="availability-list">{variant.availability.length === 0 ? <span>Chưa gán location</span> : variant.availability.map((item) => <span key={item.location_id}>{item.location_name}: {item.quantity === null ? "chưa biết" : item.quantity}</span>)}</div></td><td>{canWrite && variant.status === "active" && <button aria-label={`Lưu trữ ${variant.variant_sku ?? `biến thể ${variant.id}`}`} className="icon-button" onClick={() => void mutate(() => api.archiveVariant(workspace.id, selected.id, variant.id), "Đã lưu trữ biến thể.")} type="button"><Archive size={15} /></button>}</td></tr>)}</tbody></table></div>}
                  {canWrite && <details className="detail-disclosure"><summary><Plus size={16} /> Thêm biến thể</summary><form className="catalog-form compact-form" onSubmit={addVariant}><div className="form-columns"><label>Variant SKU<input name="variant_sku" /></label><label>Tên<input name="variant_name" /></label></div><div className="form-columns"><label>Màu / thuộc tính<input name="color" /></label><label>Kích thước / lựa chọn<input name="size" /></label></div><div className="form-columns"><label>Giá mặc định variant<input name="price_override" inputMode="decimal" /></label><label>Tồn kho location mặc định<input name="stock_quantity" inputMode="numeric" type="number" min="0" /></label></div><button className="secondary-button" type="submit"><Plus size={16} /> Thêm biến thể</button></form></details>}
                </section>
              )}

              {activeTab === "images" && (
                <section aria-labelledby="product-tab-images" id="product-panel-images" role="tabpanel">
                  <div className="detail-section-heading"><div><h3>Hình ảnh sản phẩm</h3><p>Ảnh chung dùng cho sản phẩm; ảnh biến thể chỉ đại diện cho lựa chọn tương ứng.</p></div><span className="image-count-badge">{activeImages.length} ảnh</span></div>
                  <div className="image-list compact-image-list">{selected.images.length === 0 && <p className="detail-empty">Chưa có ảnh.</p>}{selected.images.map((image) => <article key={image.id}>{renderImageThumbnail(image)}<div><strong>{imageName(image)}</strong><small>{imageVariantLabel(image)} · {image.status === "cleanup_pending" ? "Chờ dọn dẹp Storage" : image.status}</small></div>{image.status === "active" && <button className="text-button" onClick={async () => { try { const result = await api.getProductImageUrl(workspace.id, selected.id, image.id); window.open(result.url, "_blank", "noopener,noreferrer"); } catch (caught) { setError(errorMessage(caught)); } }} type="button">Xem</button>}{canWrite && image.status === "active" && <button className="text-button danger-text" onClick={() => void mutate(() => api.deleteProductImage(workspace.id, selected.id, image.id), "Đã cập nhật trạng thái dọn ảnh.")} type="button">Xóa</button>}{canWrite && image.status === "cleanup_pending" && <button className="text-button" onClick={() => void mutate(() => api.retryImageCleanup(workspace.id, selected.id, image.id), "Đã thử dọn ảnh lại.")} type="button"><RefreshCw size={14} /> Thử lại</button>}</article>)}</div>
                  {canWrite && <form className="catalog-form image-upload-form" onSubmit={uploadImage}><label>Gắn với<select name="variant_id"><option value="">Ảnh chung</option>{selected.variants.filter((variant) => variant.status === "active").map((variant) => <option key={variant.id} value={variant.id}>{variant.variant_sku ?? variant.name ?? `Biến thể #${variant.id}`}</option>)}</select></label><label>Chọn ảnh<input accept="image/png,image/jpeg,image/webp" name="file" required type="file" /></label><label>Alt text<input name="alt_text" maxLength={300} /></label><button className="secondary-button" type="submit"><ImagePlus size={17} /> Tải ảnh lên</button><small>PNG, JPEG hoặc WebP · tối đa 5 MB · nội dung được backend xác minh.</small></form>}
                </section>
              )}

              {activeTab === "guide" && (
                <section aria-labelledby="product-tab-guide" id="product-panel-guide" role="tabpanel">
                  <div className="detail-section-heading"><div><h3>Hướng dẫn tùy chọn</h3><p>Sản phẩm không bắt buộc có hướng dẫn kích thước.</p></div></div>
                  {canWrite ? <form className="catalog-form guide-form" onSubmit={saveSizeGuide}><label>Tiêu đề<input defaultValue={selected.size_guide?.title ?? "Hướng dẫn kích thước"} name="title" required /></label><label>Nội dung JSON<textarea defaultValue={JSON.stringify(selected.size_guide?.content ?? { columns: ["Size", "Thông số"], rows: [] }, null, 2)} name="content" rows={10} required /></label><button className="secondary-button" type="submit">Lưu hướng dẫn</button></form> : <pre className="guide-preview">{JSON.stringify(selected.size_guide?.content ?? {}, null, 2)}</pre>}
                </section>
              )}
            </div>
          </aside>
        )}
      </div>
    </AppShell>
  );
}
