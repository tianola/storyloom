import type { ElementState, SceneState } from "./scene-state.ts";

export type SvgOptions = { width: number; height: number };

const BACKGROUND = "#0b1118";
const GRID = "#152230";

const FONT_SIZES: Record<ElementState["role"], number> = {
  title: 66,
  panel: 46,
  value: 78,
  node: 42,
  caption: 34,
  bar: 0,
  link: 0,
  packet: 0,
  axis: 0
};

function escapeText(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function num(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

/** Average glyph advance for the sans resvg falls back to, as a fraction of the font size. Measured by rendering: a
 * 22-character step label needs 0.52 to fill a 496px node, 0.60 leaves a third of the box empty and 0.45 overflows. */
export const AVERAGE_ADVANCE = 0.52;
export const MIN_FONT_SIZE = 24;

function wrap(text: string, maxChars: number): string[] {
  const lines: string[] = [];
  let current = "";
  for (const word of text.split(" ")) {
    if (current === "") current = word;
    else if (current.length + 1 + word.length <= maxChars) current = `${current} ${word}`;
    else {
      lines.push(current);
      current = word;
    }
  }
  if (current !== "") lines.push(current);
  return lines;
}

function shapeOf(element: ElementState): string {
  switch (element.role) {
    case "panel":
    case "node":
      return `<rect x="0" y="0" width="${num(element.width)}" height="${num(element.height)}" rx="28" fill="${element.fill}" stroke="#2a3d52" stroke-width="3"/>`;
    case "bar": {
      const drawn = element.height * element.grow;
      return `<rect x="0" y="${num(element.height - drawn)}" width="${num(element.width)}" height="${num(drawn)}" rx="10" fill="${element.fill}"/>`;
    }
    case "link": {
      const length = element.width;
      const offset = length * (1 - element.drawProgress);
      return `<line x1="0" y1="${num(element.height / 2)}" x2="${num(length)}" y2="${num(element.height / 2)}" stroke="${element.fill}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${num(length)}" stroke-dashoffset="${num(offset)}"/>`;
    }
    case "packet": {
      const radius = element.width / 2;
      return `<circle cx="${num(radius)}" cy="${num(radius)}" r="${num(radius)}" fill="${element.fill}"/>`;
    }
    case "axis":
      return `<line x1="0" y1="0" x2="${num(element.width)}" y2="0" stroke="${element.fill}" stroke-width="4"/>`;
    default:
      return "";
  }
}

function textOf(element: ElementState): string {
  if (element.text === "" || (element.role !== "title" && element.role !== "panel" && element.role !== "value" && element.role !== "node" && element.role !== "caption")) {
    return "";
  }
  const base = FONT_SIZES[element.role];
  const lines = wrap(element.text, Math.max(1, Math.floor(element.width / (base * AVERAGE_ADVANCE))));
  const longest = Math.max(1, ...lines.map((line) => line.length));
  const size = Math.max(MIN_FONT_SIZE, Math.min(base, Math.floor(element.width / (longest * AVERAGE_ADVANCE))));
  const bold = element.role === "title" || element.role === "value";
  const centerY = element.role === "panel" ? size + 16 : element.height / 2;
  const weight = bold ? " font-weight=\"700\"" : "";
  // panel and node text sits on top of that shape's own fill, so it can never be colored by it
  const color = element.role === "panel" || element.role === "node" ? "#f2f5f8" : element.fill;
  const lineHeight = Math.round(size * 1.18);
  const first = centerY - ((lines.length - 1) * lineHeight) / 2;
  const spans = lines.map((line, index) => `<tspan x="${num(element.width / 2)}" y="${num(first + index * lineHeight)}">${escapeText(line)}</tspan>`).join("");
  return `<text fill="${color}" font-size="${size}"${weight} text-anchor="middle" dominant-baseline="middle">${spans}</text>`;
}

function elementMarkup(element: ElementState): string {
  if (element.opacity <= 0.004) return "";
  const centerX = element.x + element.width / 2;
  const centerY = element.y + element.height / 2;
  const transform = element.scale === 1
    ? `translate(${num(element.x)} ${num(element.y)})`
    : `translate(${num(centerX)} ${num(centerY)}) scale(${num(element.scale)}) translate(${num(-element.width / 2)} ${num(-element.height / 2)})`;
  return `<g id="${escapeText(element.id)}" opacity="${num(element.opacity)}" transform="${transform}">${shapeOf(element)}${textOf(element)}</g>`;
}

export function frameSvg(state: SceneState, options: SvgOptions): string {
  const grid: string[] = [];
  for (let x = 0; x <= options.width; x += 120) grid.push(`<line x1="${x}" y1="0" x2="${x}" y2="${options.height}" stroke="${GRID}" stroke-width="1"/>`);
  for (let y = 0; y <= options.height; y += 120) grid.push(`<line x1="0" y1="${y}" x2="${options.width}" y2="${y}" stroke="${GRID}" stroke-width="1"/>`);
  const ordered = [...state.elements.values()].sort((a, b) => (a.id > b.id ? 1 : -1));
  const body = ordered.map(elementMarkup).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${options.width}" height="${options.height}" viewBox="0 0 ${options.width} ${options.height}"><rect width="${options.width}" height="${options.height}" fill="${BACKGROUND}"/><g>${grid.join("")}</g>${body}</svg>`;
}
