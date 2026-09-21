import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  it("exposes navigation and a main landmark without pretending future features work", () => {
    render(
      <AppShell>
        <h1>Tổng quan</h1>
      </AppShell>,
    );

    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tổng quan" })).toBeInTheDocument();
    expect(screen.getAllByText("Sắp triển khai")).not.toHaveLength(0);
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });
});
