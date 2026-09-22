import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CatalogPage } from "./catalog-page";

const mocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  listProducts: vi.fn(),
  createProduct: vi.fn(),
  previewCatalogImport: vi.fn(),
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
      previewCatalogImport: mocks.previewCatalogImport,
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

  it("shows row-level CSV preview before enabling import", async () => {
    mocks.previewCatalogImport.mockResolvedValue({
      payload_sha256: "a".repeat(64),
      product_count: 2,
      variant_count: 2,
      errors: [{ row: 3, column: "variant_sku", code: "DUPLICATE", message: "SKU bị trùng" }],
    });
    render(<CatalogPage />);
    await screen.findByText("Sản phẩm chưa có");
    const file = new File(["product_sku,name"], "catalog.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/Chọn CSV UTF-8/), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra dữ liệu" }));

    expect(await screen.findByText(/Dòng 3, variant_sku: SKU bị trùng/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Import catalog" })).not.toBeInTheDocument();
  });
});
