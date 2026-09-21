import { describe, expect, it } from "vitest";

import { getWidgetPackageInfo } from "./index";

describe("widget package scaffold", () => {
  it("does not claim to be a functional widget", () => {
    expect(getWidgetPackageInfo()).toEqual({ status: "scaffold", functional: false });
  });
});
