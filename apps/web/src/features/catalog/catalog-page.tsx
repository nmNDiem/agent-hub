"use client";

import {
  Archive,
  Boxes,
  ChevronRight,
  ImagePlus,
  LoaderCircle,
  PackagePlus,
  Plus,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import {
  api,
  ApiError,
  type Me,
  type ProductDetail,
  type ProductSummary,
  type Workspace,
} from "@/lib/api";
import { CatalogImportWizard } from "./catalog-import-wizard";

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

export function CatalogPage() {
  const params = useParams<{ workspaceSlug: string }>();
  const router = useRouter();
  const [me, setMe] = useState<Me>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("active");
  const [selected, setSelected] = useState<ProductDetail>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});

  const canWrite = workspace?.role === "owner" || workspace?.role === "admin";

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
    if (!workspace || !selected) {
      return () => { active = false; };
    }
    const images = selected.images.filter((image) => image.status === "active");
    Promise.all(images.map(async (image) => {
      const result = await api.getProductImageUrl(workspace.id, selected.id, image.id);
      return [image.id, result.url] as const;
    })).then((entries) => {
      if (active) setImageUrls(Object.fromEntries(entries));
    }).catch(() => {
      if (active) setImageUrls({});
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
      setError("Nội dung size guide phải là JSON hợp lệ.");
      return;
    }
    await mutate(
      () => api.putSizeGuide(workspace.id, selected.id, { title: text(form, "title"), content }),
      "Đã lưu hướng dẫn kích thước.",
    );
  }

  async function uploadImage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspace || !selected) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await mutate(
      () => api.uploadProductImage(workspace.id, selected.id, form),
      "Đã tải ảnh lên kho riêng tư.",
    );
    formElement.reset();
  }

  if (loading) return <main className="center-state" aria-live="polite">Đang tải catalog…</main>;
  if (!me || !workspace) return <main className="center-state"><p role="alert">{error}</p></main>;

  return (
    <AppShell user={me.user} workspaces={me.workspaces} workspace={workspace}>
      <section className="page-heading catalog-heading">
        <div><p className="eyebrow">Catalog có cấu trúc</p><h1>Sản phẩm</h1><p>Giá, biến thể và tồn kho là nguồn dữ liệu xác thực cho chatbot.</p></div>
        {canWrite && <a className="primary-button compact-button" href="#create-product"><PackagePlus size={18} /> Thêm sản phẩm</a>}
      </section>

      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="success-message" role="status">{notice}</p>}

      <section className="catalog-toolbar" aria-label="Bộ lọc catalog">
        <form onSubmit={(event) => { event.preventDefault(); void refreshProducts(); }}>
          <label className="search-field"><Search size={18} aria-hidden="true" /><span className="sr-only">Tìm sản phẩm</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tên hoặc SKU" /></label>
          <label><span className="sr-only">Trạng thái</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="active">Đang hoạt động</option><option value="archived">Đã lưu trữ</option><option value="">Tất cả</option></select></label>
          <button className="secondary-button" disabled={busy} type="submit">Lọc</button>
        </form>
        {busy && <LoaderCircle className="spinner" aria-label="Đang xử lý" size={20} />}
      </section>

      <div className="catalog-layout">
        <section className="catalog-list-card" aria-labelledby="catalog-list-title">
          <div className="card-heading"><div><h2 id="catalog-list-title">Danh sách sản phẩm</h2><p>{products.length} bản ghi đang hiển thị</p></div><Boxes aria-hidden="true" /></div>
          {products.length === 0 ? (
            <div className="catalog-empty"><Boxes size={38} /><h3>Sản phẩm chưa có</h3><p>Tạo thủ công hoặc dùng CSV để nhập catalog.</p></div>
          ) : (
            <div className="product-table" role="table" aria-label="Sản phẩm">
              <div className="product-row product-table-head" role="row"><span>Tên / SKU</span><span>Giá</span><span>Biến thể</span><span>Trạng thái</span><span /></div>
              {products.map((product) => (
                <div className="product-row" role="row" key={product.id}>
                  <span><strong>{product.name}</strong><small>{product.product_sku ?? "Không có SKU"} · {product.category ?? "Chưa phân loại"}</small></span>
                  <span>{formatPrice(product.price, product.currency)}</span>
                  <span>{product.variant_count}</span>
                  <span><i className={`status-pill ${product.status}`}>{product.status === "active" ? "Hoạt động" : "Lưu trữ"}</i></span>
                  <button aria-label={`Quản lý ${product.name}`} className="icon-button" onClick={() => void openProduct(product.id)} type="button"><ChevronRight size={18} /></button>
                </div>
              ))}
            </div>
          )}
          {nextCursor && <button className="load-more" disabled={busy} onClick={() => void refreshProducts(nextCursor, true)} type="button">Tải thêm</button>}
        </section>

        {canWrite && (
          <aside className="catalog-actions">
            <details className="action-card" id="create-product" open={products.length === 0}>
              <summary><Plus size={18} /> Tạo sản phẩm thủ công</summary>
              <form className="catalog-form" onSubmit={createProduct}>
                <label>Tên sản phẩm<input name="name" required maxLength={200} /></label>
                <div className="form-columns"><label>Product SKU<input name="product_sku" maxLength={100} /></label><label>Danh mục<input name="category" maxLength={120} /></label></div>
                <div className="form-columns"><label>Giá<input name="price" inputMode="decimal" placeholder="Để trống nếu chưa biết" /></label><label>Tiền tệ<input name="currency" defaultValue="VND" maxLength={3} required /></label></div>
                <label>URL sản phẩm<input name="product_url" type="url" /></label>
                <button className="primary-button" disabled={busy} type="submit">Tạo sản phẩm</button>
              </form>
            </details>

            <CatalogImportWizard
              workspaceId={workspace.id}
              onCommitted={async () => { await refreshProducts(); }}
            />
          </aside>
        )}
      </div>

      {selected && (
        <section className="product-editor" aria-labelledby="product-editor-title">
          <div className="editor-header"><div><p className="eyebrow">Chi tiết #{selected.id}</p><h2 id="product-editor-title">{selected.name}</h2></div><button aria-label="Đóng chi tiết" className="icon-button" onClick={() => { setSelected(undefined); setImageUrls({}); }} type="button"><X size={20} /></button></div>
          <form className="catalog-form product-fields" onSubmit={updateProduct}>
            <div className="form-columns"><label>Tên<input defaultValue={selected.name} name="name" required /></label><label>Product SKU<input defaultValue={selected.product_sku ?? ""} name="product_sku" /></label></div>
            <label>Mô tả<textarea defaultValue={selected.description ?? ""} name="description" rows={3} /></label>
            <div className="form-columns"><label>Danh mục<input defaultValue={selected.category ?? ""} name="category" /></label><label>URL<input defaultValue={selected.product_url ?? ""} name="product_url" type="url" /></label></div>
            <div className="form-columns"><label>Giá<input defaultValue={selected.price ?? ""} name="price" inputMode="decimal" /></label><label>Tiền tệ<input defaultValue={selected.currency} name="currency" required maxLength={3} /></label></div>
            {canWrite && <div className="form-actions"><button className="primary-button" disabled={busy} type="submit">Lưu thay đổi</button>{selected.status === "active" && <button className="danger-button" disabled={busy} onClick={() => { if (confirm("Lưu trữ sản phẩm này? SKU vẫn được giữ chỗ.")) void mutate(() => api.archiveProduct(workspace.id, selected.id), "Đã lưu trữ sản phẩm.", false).then(() => setSelected(undefined)); }} type="button"><Archive size={17} /> Lưu trữ</button>}</div>}
          </form>

          <div className="editor-grid">
            <section className="editor-section"><h3>Biến thể</h3>{selected.variants.length === 0 && <p className="muted-copy">Sản phẩm này không có biến thể.</p>}<div className="variant-list">{selected.variants.map((variant) => <article key={variant.id}><div><strong>{variant.name ?? variant.variant_sku ?? `Biến thể #${variant.id}`}</strong><small>{[variant.color, variant.size].filter(Boolean).join(" · ") || "Không có thuộc tính"}</small></div><div><span>{formatPrice(variant.effective_price, selected.currency)}</span><small>{variant.stock_quantity === null ? "Tồn kho chưa biết" : `Tồn kho: ${variant.stock_quantity}`}</small></div>{canWrite && variant.status === "active" && <button aria-label="Lưu trữ biến thể" className="icon-button" onClick={() => void mutate(() => api.archiveVariant(workspace.id, selected.id, variant.id), "Đã lưu trữ biến thể.")} type="button"><Archive size={16} /></button>}</article>)}</div>{canWrite && <form className="catalog-form compact-form" onSubmit={addVariant}><div className="form-columns"><label>Variant SKU<input name="variant_sku" /></label><label>Tên<input name="variant_name" /></label></div><div className="form-columns"><label>Màu / thuộc tính<input name="color" /></label><label>Kích thước / lựa chọn<input name="size" /></label></div><div className="form-columns"><label>Giá override<input name="price_override" inputMode="decimal" /></label><label>Tồn kho<input name="stock_quantity" inputMode="numeric" type="number" min="0" /></label></div><button className="secondary-button" type="submit"><Plus size={16} /> Thêm biến thể</button></form>}</section>

            <section className="editor-section"><h3>Hướng dẫn tùy chọn</h3><p className="muted-copy">Dữ liệu JSON linh hoạt; sản phẩm không bắt buộc có size guide.</p>{canWrite ? <form className="catalog-form compact-form" onSubmit={saveSizeGuide}><label>Tiêu đề<input defaultValue={selected.size_guide?.title ?? "Hướng dẫn kích thước"} name="title" required /></label><label>Nội dung JSON<textarea defaultValue={JSON.stringify(selected.size_guide?.content ?? { columns: ["Size", "Thông số"], rows: [] }, null, 2)} name="content" rows={7} required /></label><button className="secondary-button" type="submit">Lưu hướng dẫn</button></form> : <pre>{JSON.stringify(selected.size_guide?.content ?? {}, null, 2)}</pre>}</section>

            <section className="editor-section"><h3>Ảnh riêng tư</h3><div className="image-list">{selected.images.length === 0 && <p className="muted-copy">Chưa có ảnh.</p>}{selected.images.map((image) => <article key={image.id}>{imageUrls[image.id] && <button aria-label={`Xem ${image.alt_text ?? image.original_filename}`} className="image-thumbnail" onClick={() => window.open(imageUrls[image.id], "_blank", "noopener,noreferrer")} style={{ backgroundImage: `url(${imageUrls[image.id]})` }} type="button" />}<div><strong>{image.original_filename}</strong><small>{image.status === "cleanup_pending" ? "Chờ dọn dẹp Storage" : image.status}</small></div>{image.status === "active" && <button className="text-button" onClick={async () => { try { const result = await api.getProductImageUrl(workspace.id, selected.id, image.id); window.open(result.url, "_blank", "noopener,noreferrer"); } catch (caught) { setError(errorMessage(caught)); } }} type="button">Xem</button>}{canWrite && image.status === "active" && <button className="text-button danger-text" onClick={() => void mutate(() => api.deleteProductImage(workspace.id, selected.id, image.id), "Đã cập nhật trạng thái dọn ảnh.")} type="button">Xóa</button>}{canWrite && image.status === "cleanup_pending" && <button className="text-button" onClick={() => void mutate(() => api.retryImageCleanup(workspace.id, selected.id, image.id), "Đã thử dọn ảnh lại.")} type="button"><RefreshCw size={14} /> Thử lại</button>}</article>)}</div>{canWrite && <form className="catalog-form compact-form" onSubmit={uploadImage}><label className="upload-dropzone"><ImagePlus size={20} /><span>PNG, JPEG hoặc WebP</span><small>Tối đa 5 MB; backend xác minh nội dung thật.</small><input accept="image/png,image/jpeg,image/webp" name="file" required type="file" /></label><label>Alt text<input name="alt_text" maxLength={300} /></label><button className="secondary-button" type="submit">Tải ảnh</button></form>}</section>
          </div>
        </section>
      )}
    </AppShell>
  );
}
