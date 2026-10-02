export const palettes = ["aurora", "lagoon", "ember"] as const;

export type Palette = (typeof palettes)[number];

export const defaultPalette: Palette = "lagoon";
export const paletteStorageKey = "agenthub.palette";

export const paletteLabels: Record<Palette, string> = {
  aurora: "Aurora",
  lagoon: "Lagoon",
  ember: "Ember",
};

export function isPalette(value: unknown): value is Palette {
  return typeof value === "string" && palettes.some((palette) => palette === value);
}

export function readStoredPalette(): Palette {
  try {
    const stored = window.localStorage.getItem(paletteStorageKey);
    return isPalette(stored) ? stored : defaultPalette;
  } catch {
    return defaultPalette;
  }
}

export function applyPalette(palette: Palette): void {
  document.documentElement.dataset.palette = palette;
}

export function storePalette(palette: Palette): void {
  applyPalette(palette);
  try {
    window.localStorage.setItem(paletteStorageKey, palette);
  } catch {
    // The selected palette still applies for this page when browser storage is unavailable.
  }
}
