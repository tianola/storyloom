import { FRAMES, clamp01, easeInOutCubic, easeOutCubic, lerp, progress } from "./animation.ts";
import type { SceneSpec, TimedScene } from "./contracts.ts";

export type ElementRole = "title" | "panel" | "bar" | "value" | "node" | "link" | "packet" | "axis" | "caption";

export type ElementState = {
  id: string;
  role: ElementRole;
  x: number;
  y: number;
  width: number;
  height: number;
  opacity: number;
  scale: number;
  grow: number;
  drawProgress: number;
  text: string;
  fill: string;
};

export type SceneState = { sceneId: string; kind: SceneSpec["kind"]; frame: number; elements: Map<string, ElementState> };
export type StyleOptions = { width: number; height: number; sampleRate: number; frameRate: number };

const PALETTE = {
  ink: "#f2f5f8",
  muted: "#8fa1b3",
  primary: "#f5c85c",
  secondary: "#5ec8f5",
  panel: "#16202b",
  link: "#46607a"
};

type Anchor = {
  id: string;
  role: ElementRole;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  fill: string;
  number: number | null;
};

type Layout = { anchors: Anchor[]; groups: Map<string, string[]> };

function anchor(id: string, role: ElementRole, x: number, y: number, width: number, height: number, text = "", fill = PALETTE.ink, number: number | null = null): Anchor {
  return { id, role, x, y, width, height, text, fill, number };
}

export function formatValue(value: number): string {
  return Math.abs(value) >= 100 ? String(Math.round(value)) : value.toFixed(1);
}

/** When a bar's own label names the thing it plots, colouring by rank contradicts it: the delivered episode drew
 * "Green 530 nm" in gold because it was the tallest bar. Only the fallback changes — an explicit colour still wins. */
const LABEL_COLOURS: Record<string, string> = {
  red: "#e8564f",
  orange: "#f08c3a",
  amber: "#f5b13c",
  yellow: "#f5c85c",
  green: "#4fc47f",
  teal: "#3fc0ad",
  cyan: "#5ec8f5",
  blue: "#4f7df0",
  indigo: "#6a5cf0",
  violet: "#9b5cf0",
  purple: "#9b5cf0"
};

function colourFromLabel(label: string): string | undefined {
  for (const word of label.toLowerCase().split(/[^a-z]+/u)) {
    const colour = LABEL_COLOURS[word];
    if (colour) return colour;
  }
  return undefined;
}

function propsOf(scene: TimedScene): Record<string, unknown> {
  return scene.props as Record<string, unknown>;
}

function titleAnchor(scene: TimedScene, style: StyleOptions): Anchor {
  const props = propsOf(scene);
  return anchor("title", "title", Math.round(style.width * 0.15), Math.round(style.height * 0.08), Math.round(style.width * 0.7), Math.round(style.height * 0.09), String(props.title ?? scene.id));
}

function layoutFor(scene: TimedScene, style: StyleOptions): Layout {
  const title = titleAnchor(scene, style);
  const props = propsOf(scene);

  if (scene.kind === "process") {
    const steps = (props.steps as string[] | undefined) ?? [];
    const columns = Math.max(2, steps.length);
    const rowWidth = Math.round(style.width * 0.9);
    const gap = Math.round(style.width * 0.06);
    // A fixed node width pushed a two-step scene to opposite edges and left a metre of nothing between the boxes, so the
    // row is distributed instead: wide enough for the label, never wider than 30% of the frame.
    const nodeWidth = Math.min(Math.round(style.width * 0.3), Math.round((rowWidth - (columns - 1) * gap) / columns));
    const nodeHeight = Math.round(style.height * 0.19);
    const startX = Math.round((style.width - (columns * nodeWidth + (columns - 1) * gap)) / 2);
    const centerY = Math.round(style.height * 0.52);
    const anchors: Anchor[] = [title];
    const groups = new Map<string, string[]>();
    steps.forEach((step, index) => {
      const x = startX + index * (nodeWidth + gap);
      // The label goes under the box, not inside it: the packet starts in the first box's centre, and text there was
      // drawn straight through by it.
      anchors.push(anchor(`node-${index}`, "node", x, centerY - nodeHeight / 2, nodeWidth, nodeHeight, "", PALETTE.panel));
      anchors.push(anchor(`step-${index}`, "caption", x, centerY + nodeHeight / 2 + 16, nodeWidth, 88, step, PALETTE.muted));
      groups.set(`node-${index}`, [`node-${index}`, `step-${index}`]);
      if (index < steps.length - 1) {
        anchors.push(anchor(`link-${index}`, "link", x + nodeWidth, centerY - 4, gap, 8, "", PALETTE.link));
        groups.set(`link-${index}`, [`link-${index}`]);
      }
    });
    const first = anchors[1]!;
    anchors.push(anchor("packet", "packet", first.x + Math.round(first.width / 2) - 28, centerY - 28, 56, 56, "", PALETTE.primary));
    groups.set("packet", ["packet"]);
    groups.set("title", ["title"]);
    return { anchors, groups };
  }

  if (scene.kind === "comparison") {
    const values = (props.values as { label: string; value: number; color?: string | undefined }[] | undefined) ?? [];
    const panelWidth = Math.round(style.width * 0.36);
    const panelHeight = Math.round(style.height * 0.56);
    const left = Math.round(style.width * 0.1);
    const right = Math.round(style.width * 0.9 - panelWidth);
    const top = Math.round(style.height * 0.24);
    const barWidth = Math.round(panelWidth * 0.34);
    const barMax = Math.round(panelHeight * 0.62);
    const barTop = top + panelHeight - barMax;
    const unit = String(props.unit ?? "");
    const anchors = [
      title,
      anchor("left", "panel", left, top, panelWidth, panelHeight, String(props.left ?? ""), PALETTE.panel),
      anchor("right", "panel", right, top, panelWidth, panelHeight, String(props.right ?? ""), PALETTE.panel),
      anchor("left-bar", "bar", left + Math.round((panelWidth - barWidth) / 2), barTop, barWidth, barMax, "", values[0]?.color ?? colourFromLabel(values[0]?.label ?? "") ?? PALETTE.secondary, values[0]?.value ?? 0),
      anchor("right-bar", "bar", right + Math.round((panelWidth - barWidth) / 2), barTop, barWidth, barMax, "", values[1]?.color ?? colourFromLabel(values[1]?.label ?? "") ?? PALETTE.primary, values[1]?.value ?? 0),
      anchor("left-value", "value", left, barTop - 84, panelWidth, 72, formatValue(values[0]?.value ?? 0), values[0]?.color ?? colourFromLabel(values[0]?.label ?? "") ?? PALETTE.secondary, values[0]?.value ?? 0),
      anchor("right-value", "value", right, barTop - 84, panelWidth, 72, formatValue(values[1]?.value ?? 0), values[1]?.color ?? colourFromLabel(values[1]?.label ?? "") ?? PALETTE.primary, values[1]?.value ?? 0),
      anchor("unit", "caption", left, top + panelHeight + 12, panelWidth * 2, 46, unit, PALETTE.muted)
    ];
    return {
      anchors,
      groups: new Map<string, string[]>([
        ["title", ["title"]],
        ["left", ["left", "left-bar", "left-value", "unit"]],
        ["right", ["right", "right-bar", "right-value", "unit"]],
        ["left-value", ["left-value"]],
        ["right-value", ["right-value"]]
      ])
    };
  }

  const series = (props.series as { label: string; value: number; color?: string | undefined }[] | undefined) ?? [];
  const chartLeft = Math.round(style.width * 0.12);
  const chartWidth = Math.round(style.width * 0.76);
  const chartTop = Math.round(style.height * 0.24);
  const chartHeight = Math.round(style.height * 0.5);
  const max = Math.max(1e-6, ...series.map((entry) => Math.abs(entry.value)));
  const slot = series.length > 0 ? Math.floor(chartWidth / series.length) : chartWidth;
  const barWidth = Math.max(8, Math.round(slot * 0.62));
  const peak = series.reduce((best, entry, index) => (Math.abs(entry.value) > Math.abs(series[best]!.value) ? index : best), 0);
  // The peak bar's value label must stay clear of the title, so bars fill 88% of the chart box.
  const barMax = Math.round(chartHeight * 0.88);
  const groups = new Map<string, string[]>([["title", ["title"]], ["axis", ["axis", "unit"]]]);
  const anchors: Anchor[] = [
    title,
    anchor("axis", "axis", chartLeft, chartTop + chartHeight, chartWidth, 6, "", PALETTE.muted),
    anchor("unit", "caption", chartLeft, chartTop + chartHeight + 64, chartWidth, 46, String(props.unit ?? ""), PALETTE.muted)
  ];
  series.forEach((entry, index) => {
    const barHeight = Math.max(2, Math.round((Math.abs(entry.value) / max) * barMax));
    const x = chartLeft + index * slot + Math.round((slot - barWidth) / 2);
    anchors.push(anchor(`bar-${index}`, "bar", x, chartTop + chartHeight - barHeight, barWidth, barHeight, "", entry.color ?? colourFromLabel(entry.label) ?? (index === peak ? PALETTE.primary : PALETTE.secondary), entry.value));
    anchors.push(anchor(`label-${index}`, "caption", chartLeft + index * slot, chartTop + chartHeight + 16, slot, 44, entry.label, PALETTE.muted));
    anchors.push(anchor(`value-${index}`, "value", chartLeft + index * slot, chartTop + chartHeight - barHeight - 70, slot, 56, formatValue(entry.value), PALETTE.ink, entry.value));
    groups.set(`bar-${index}`, [`bar-${index}`, `label-${index}`, `value-${index}`]);
    groups.set(`value-${index}`, [`value-${index}`]);
  });
  return { anchors, groups };
}

function fromAnchor(item: Anchor): ElementState {
  return {
    id: item.id,
    role: item.role,
    x: item.x,
    y: item.y,
    width: item.width,
    height: item.height,
    opacity: 0,
    scale: 1,
    grow: item.role === "bar" ? 0 : 1,
    drawProgress: item.role === "link" ? 0 : 1,
    text: item.text,
    fill: item.fill
  };
}

export function frameState(scene: TimedScene, frame: number, style: StyleOptions): SceneState {
  const { anchors, groups } = layoutFor(scene, style);
  const byId = new Map(anchors.map((item) => [item.id, item]));
  const elements = new Map(anchors.map((item) => [item.id, fromAnchor(item)]));
  const packet = byId.get("packet");
  if (packet) elements.get("packet")!.opacity = 1;

  const position = new Map<string, { x: number; y: number }>();
  for (const beat of scene.beatFrames) {
    const target = byId.get(beat.target);
    if (!target) throw new RangeError(`Scene ${scene.id} beats unknown element ${beat.target}`);
    if (beat.frame > frame) break;
    const members = (groups.get(beat.target) ?? [beat.target]).filter((id) => elements.has(id));
    const t = (window: number) => progress(frame, beat.frame, window);

    switch (beat.action) {
      case "reveal": {
        const eased = easeOutCubic(t(FRAMES.reveal));
        for (const id of members) {
          const element = elements.get(id)!;
          element.opacity = Math.max(element.opacity, eased);
          element.scale = lerp(0.92, 1, eased);
          if (element.role === "bar") element.grow = Math.max(element.grow, eased);
        }
        break;
      }
      case "hide": {
        const eased = easeOutCubic(t(FRAMES.hide));
        for (const id of members) elements.get(id)!.opacity = Math.min(elements.get(id)!.opacity, 1 - eased);
        break;
      }
      case "emphasize": {
        const eased = easeOutCubic(t(FRAMES.reveal));
        for (const id of members) {
          const element = elements.get(id)!;
          element.opacity = 1;
          if (element.role === "bar") element.grow = Math.max(element.grow, 1);
          element.scale = lerp(1, 1.06, eased);
        }
        break;
      }
      case "highlight": {
        const up = easeInOutCubic(t(FRAMES.highlightUp));
        const down = easeInOutCubic(progress(frame, beat.frame + FRAMES.highlightUp, FRAMES.highlightDown));
        for (const id of members) {
          const element = elements.get(id)!;
          element.opacity = 1;
          // a bar the model highlighted instead of grew would otherwise be drawn at zero height: s008 shipped labels
          // floating over an empty chart because its only beats were reveal and highlight
          if (element.role === "bar") element.grow = Math.max(element.grow, 1);
          element.scale = 1 + 0.06 * clamp01(up - down);
        }
        break;
      }
      case "grow": {
        const eased = easeOutCubic(t(FRAMES.grow));
        for (const id of members) {
          const element = elements.get(id)!;
          element.opacity = 1;
          element.grow = eased;
        }
        break;
      }
      case "draw": {
        const eased = easeInOutCubic(t(FRAMES.draw));
        const element = elements.get(beat.target)!;
        element.drawProgress = eased;
        element.opacity = 1;
        break;
      }
      case "count": {
        const eased = easeOutCubic(t(FRAMES.count));
        const element = elements.get(beat.target)!;
        const numeric = Number(target.text);
        const value = target.number ?? (Number.isFinite(numeric) ? numeric : 0);
        element.opacity = 1;
        element.text = formatValue(value * eased);
        break;
      }
      case "move": {
        const from = position.get(beat.target) ?? { x: target.x, y: target.y };
        const destination = beat.to ? byId.get(beat.to) : undefined;
        if (!destination) throw new RangeError(`Scene ${scene.id} move beat needs an existing to anchor`);
        const element = elements.get(beat.target)!;
        const slot = {
          x: destination.x + (destination.width - element.width) / 2,
          y: destination.y + (destination.height - element.height) / 2
        };
        const eased = easeInOutCubic(t(FRAMES.move));
        const x = lerp(from.x, slot.x, eased);
        const y = lerp(from.y, slot.y, eased);
        if (frame >= beat.frame + FRAMES.move) position.set(beat.target, slot);
        element.x = x;
        element.y = y;
        element.opacity = 1;
        break;
      }
      case "transform": {
        const destination = beat.to ? byId.get(beat.to) : undefined;
        if (!destination) throw new RangeError(`Scene ${scene.id} transform beat needs an existing to anchor`);
        const eased = easeInOutCubic(t(FRAMES.move));
        const element = elements.get(beat.target)!;
        element.x = lerp(target.x, destination.x, eased);
        element.y = lerp(target.y, destination.y, eased);
        element.width = lerp(target.width, destination.width, eased);
        element.height = lerp(target.height, destination.height, eased);
        element.opacity = 1;
        break;
      }
    }
  }

  return { sceneId: scene.id, kind: scene.kind, frame, elements };
}
