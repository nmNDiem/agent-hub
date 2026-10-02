"use client";

import { Check, PaletteIcon } from "lucide-react";
import { useEffect, useState } from "react";

import {
  applyPalette,
  defaultPalette,
  paletteLabels,
  palettes,
  readStoredPalette,
  storePalette,
  type Palette,
} from "@/lib/palette";

export function PalettePicker() {
  const [palette, setPalette] = useState<Palette>(defaultPalette);

  useEffect(() => {
    const stored = readStoredPalette();
    applyPalette(stored);
    const timeout = window.setTimeout(() => setPalette(stored), 0);
    return () => window.clearTimeout(timeout);
  }, []);

  function selectPalette(nextPalette: Palette) {
    setPalette(nextPalette);
    storePalette(nextPalette);
  }

  return (
    <details className="palette-picker">
      <summary aria-label={`Phối màu hiện tại: ${paletteLabels[palette]}`}>
        <PaletteIcon aria-hidden="true" size={18} />
      </summary>
      <div aria-label="Chọn phối màu" className="palette-menu" role="group">
        <div className="palette-menu-heading">
          <strong>Phối màu</strong>
          <small>Mặc định: Lagoon</small>
        </div>
        {palettes.map((item) => (
          <button
            aria-pressed={palette === item}
            key={item}
            onClick={() => selectPalette(item)}
            type="button"
          >
            <span aria-hidden="true" className={`palette-swatch ${item}`} />
            <span>{paletteLabels[item]}</span>
            {palette === item && <Check aria-hidden="true" size={16} />}
          </button>
        ))}
      </div>
    </details>
  );
}
