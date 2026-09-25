import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CatalogPage } from "./catalog-page";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  listProducts: vi.fn(),
  createProduct: vi.fn(),
  createCatalogImport: vi.fn(),
  resolveCatalogImportIssue: vi.fn(),
  commitCatalogImportJob: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ workspaceSlug: "fashion-shop" }),
  usePathname: () => "/app/fashion-shop/products",
  useRouter: () => ({ push: vi.fn(), replace: mocks.replace, refresh: vi.fn() }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...original,
    api: {
      ...original.api,
      getMe: mocks.getMe,
      listProducts: mocks.listProducts,
      createProduct: mocks.createProduct,
      createCatalogImport: mocks.createCatalogImport,
      resolveCatalogImportIssue: mocks.resolveCatalogImportIssue,
      commitCatalogImportJob: mocks.commitCatalogImportJob,
    },
  };
});

const workspace = {
  id: "01992f3c-4436-7000-8000-000000000001",
  slug: "fashion-shop",
  display_name: "Fashion Shop",
  timezone: "Asia/Ho_Chi_Minh",
  role: "owner" as const,
  created_at: "2026-09-21T00:00:00Z",
};

describe("CatalogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getMe.mockResolvedValue({
      user: { id: "user", email: "owner@example.com", email_verified: true },
      workspaces: [workspace],
    });
    mocks.listProducts.mockResolvedValue({ items: [], next_cursor: null });
    mocks.createProduct.mockResolvedValue({
      id: 1,
      product_sku: "SKU-1",
      name: "Áo sơ mi",
      category: null,
      currency: "VND",
      price: null,
      status: "active",
      variant_count: 0,
      created_at: "2026-09-22T00:00:00Z",
      updated_at: "2026-09-22T00:00:00Z",
      description: null,
      product_url: null,
      variants: [],
      size_guide: null,
      images: [],
    });
  });

  it("renders the real empty state and creates a product without variants", async () => {
    render(<CatalogPage />);
    expect(await screen.findByText("Sản phẩm chưa có")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Tên sản phẩm"), {
      target: { value: "Áo sơ mi" },
    });
    fireEvent.change(screen.getByLabelText("Product SKU"), {
      target: { value: "sku-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Tạo sản phẩm" }));

    await waitFor(() => expect(mocks.createProduct).toHaveBeenCalledWith(
      workspace.id,
      expect.objectContaining({ name: "Áo sơ mi", product_sku: "sku-1", price: null }),
    ));
    expect(await screen.findByText("Sản phẩm này không có biến thể.")).toBeInTheDocument();
  });

  it("shows only unresolved questions after universal file analysis", async () => {
    mocks.createCatalogImport.mockResolvedValue({
      id: 7,
      status: "needs_confirmation",
      original_filename: "catalog.xlsx",
      file_type: "xlsx",
      schema_fingerprint: "a".repeat(64),
      summary: {
        products: { create: 2, update: 0, unchanged: 0, conflict: 0 },
        variants: { create: 2, update: 0, unchanged: 0, conflict: 0 },
        images: { create: 0, update: 0, unchanged: 0, conflict: 0 },
      },
      issues: [{ id: 3, issue_type: "AMBIGUOUS_COLUMN", severity: "needs_confirmation", message: "Cột Mã hàng có vẻ là SKU.", source_location: { sheet: "Data", row: 1 }, evidence: {}, options: [], status: "open" }],
      metadata: { rows: 2 },
      result: null,
      created_at: "2026-09-25T00:00:00Z",
      updated_at: "2026-09-25T00:00:00Z",
    });
    render(<CatalogPage />);
    await screen.findByText("Sản phẩm chưa có");
    const file = new File(["workbook"], "catalog.xlsx");
    fireEvent.change(screen.getByLabelText("Chọn tệp catalog"), { target: { files: [file] } });

    expect(await screen.findByText("Cột Mã hàng có vẻ là SKU.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nhập catalog" })).toBeDisabled();
  });
});
