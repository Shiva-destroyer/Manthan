import type { ReactNode } from "react";

// Converted once from design/icons/*.svg so no raw SVG string is ever injected as HTML.
// Each icon is drawn on a 24 x 24 grid with a 1.5 stroke in currentColor.
const ICONS: Record<string, ReactNode> = {
  "data-sink": (
    <>
      <path d="M4 4 H20 L14 11 V16 H10 V11 Z"/>
      <path d="M5 20 H19"/>
      <path d="M12 16 V18"/>
    </>
  ),
  "document-store": (
    <>
      <path d="M8 3 H15 L19 7 V17 H8 Z"/>
      <path d="M15 3 V7 H19"/>
      <path d="M5 6 V20 H16"/>
      <path d="M11 11 H16"/>
      <path d="M11 14 H14"/>
    </>
  ),
  "embedder": (
    <>
      <path d="M3 8 H9"/>
      <path d="M3 12 H8"/>
      <path d="M3 16 H9"/>
      <path d="M11 12 H13.5"/>
      <circle cx="16.5" cy="8" r="0.9"/>
      <circle cx="20" cy="8" r="0.9"/>
      <circle cx="16.5" cy="12" r="0.9"/>
      <circle cx="20" cy="12" r="0.9"/>
      <circle cx="16.5" cy="16" r="0.9"/>
      <circle cx="20" cy="16" r="0.9"/>
    </>
  ),
  "guard": (
    <>
      <path d="M12 3 L19 6 V11.5 C19 16 16 19.5 12 21 C8 19.5 5 16 5 11.5 V6 Z"/>
      <path d="M8 12 H16"/>
    </>
  ),
  "internet-blocked": (
    <>
      <circle cx="12" cy="12" r="8"/>
      <path d="M4 12 H20"/>
      <path d="M12 4 C9.5 6.5 9.5 17.5 12 20"/>
      <path d="M12 4 C14.5 6.5 14.5 17.5 12 20"/>
      <path d="M5 19 L19 5"/>
    </>
  ),
  "mcp-server-malicious": (
    <>
      <rect x="4" y="6" width="13" height="12" rx="2"/>
      <path d="M17 12 H19.5 L21 10"/>
      <path d="M19.5 12 L21 14"/>
      <path d="M7.5 10 L9.5 12 L7.5 14"/>
      <path d="M11.5 14 H13.5"/>
    </>
  ),
  "mcp-server": (
    <>
      <rect x="4" y="6" width="13" height="12" rx="2"/>
      <path d="M17 10 H20.5"/>
      <path d="M17 14 H20.5"/>
      <path d="M7.5 10 H12"/>
      <path d="M7.5 14 H10"/>
    </>
  ),
  "ollama-host": (
    <>
      <rect x="6" y="6" width="12" height="12" rx="2"/>
      <rect x="9.5" y="9.5" width="5" height="5" rx="1"/>
      <path d="M9 3 V6"/>
      <path d="M15 3 V6"/>
      <path d="M9 18 V21"/>
      <path d="M15 18 V21"/>
      <path d="M3 9 H6"/>
      <path d="M3 15 H6"/>
      <path d="M18 9 H21"/>
      <path d="M18 15 H21"/>
    </>
  ),
  "question": (
    <>
      <path d="M4 5 H20 V16 H11 L7 20 V16 H4 Z"/>
      <path d="M10 8.8 C10 7.6 11 7 12 7 C13.1 7 14 7.7 14 8.8 C14 10.2 12 10.4 12 11.8"/>
      <circle cx="12" cy="13.6" r="0.4"/>
    </>
  ),
  "results-store": (
    <>
      <ellipse cx="12" cy="6" rx="7" ry="2.5"/>
      <path d="M5 6 V18 C5 19.4 8.1 20.5 12 20.5 C15.9 20.5 19 19.4 19 18 V6"/>
      <path d="M5 12 C5 13.4 8.1 14.5 12 14.5 C15.9 14.5 19 13.4 19 12"/>
    </>
  ),
  "rubric-judge": (
    <>
      <path d="M12 4 V20"/>
      <path d="M8 20 H16"/>
      <path d="M5 7 H19"/>
      <path d="M5 7 L3 13 C3.8 14.4 6.2 14.4 7 13 Z"/>
      <path d="M19 7 L17 13 C17.8 14.4 20.2 14.4 21 13 Z"/>
    </>
  ),
  "rule-check": (
    <>
      <path d="M5 6 H14"/>
      <path d="M5 10.5 H11"/>
      <path d="M5 15 H9"/>
      <path d="M12.5 16 L15 18.5 L20 12.5"/>
    </>
  ),
  "sandbox": (
    <>
      <path d="M3 8 V4 H7"/>
      <path d="M17 4 H21 V8"/>
      <path d="M21 16 V20 H17"/>
      <path d="M7 20 H3 V16"/>
      <rect x="8" y="8" width="8" height="8" rx="1.5"/>
    </>
  ),
};

export const hasIcon = (name: string) => name in ICONS;

// Draws the icon inside an svg, centred on (cx, cy), `size` units wide.
export function Icon({ name, cx, cy, size }: { name: string; cx: number; cy: number; size: number }) {
  if (!hasIcon(name)) return null;
  return (
    <g
      transform={`translate(${cx - size / 2} ${cy - size / 2}) scale(${size / 24})`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONS[name]}
    </g>
  );
}
