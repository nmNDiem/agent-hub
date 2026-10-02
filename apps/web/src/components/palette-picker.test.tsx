import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { paletteStorageKey } from "@/lib/palette";

import { PalettePicker } from "./palette-picker";

describe("PalettePicker", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.dataset.palette = "lagoon";
  });

  it("uses Lagoon when there is no valid stored palette", async () => {
    window.localStorage.setItem(paletteStorageKey, "not-a-palette");
    render(<PalettePicker />);

    await waitFor(() => expect(document.documentElement.dataset.palette).toBe("lagoon"));
    expect(screen.getByLabelText("Phối màu hiện tại: Lagoon")).toBeInTheDocument();
  });

  it("restores and persists an allowed palette", async () => {
    window.localStorage.setItem(paletteStorageKey, "ember");
    render(<PalettePicker />);

    await waitFor(() => expect(document.documentElement.dataset.palette).toBe("ember"));
    fireEvent.click(screen.getByRole("button", { name: "Aurora" }));

    expect(document.documentElement.dataset.palette).toBe("aurora");
    expect(window.localStorage.getItem(paletteStorageKey)).toBe("aurora");
  });
});
