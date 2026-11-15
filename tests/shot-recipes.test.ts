import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const ROOT = join(import.meta.dirname, "..", "work", "shot-recipes");
const HTML_PATH = join(ROOT, "index.html");

/** Extract the inline <script> block (the one without a src attribute). */
function getInlineScript(htmlStr: string): string {
  const allScripts = [...htmlStr.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)];
  for (const m of allScripts) {
    if (!m[1]!.includes("src=") && m[2]!.trim().length > 0) return m[2]!;
  }
  return "";
}

let html: string;

test("shot-recipes: composition HTML file exists", async () => {
  html = await readFile(HTML_PATH, "utf-8");
  assert.ok(html.length > 0, "index.html must not be empty");
});

test("shot-recipes: root composition is 1920x1080 with duration 16", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");
  assert.match(html, /data-composition-id="main"/, "must have composition id 'main'");
  assert.match(html, /data-width="1920"/, "must be 1920 wide");
  assert.match(html, /data-height="1080"/, "must be 1080 tall");
  assert.match(html, /data-duration="16"/, "must be 16 seconds total");
});

test("shot-recipes: all four section IDs exist with correct timing", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const sections = [
    { id: "recreated-ui", start: "0", duration: "4" },
    { id: "kinetic-quote", start: "4", duration: "4" },
    { id: "ken-burns", start: "8", duration: "4" },
    { id: "news-lower-third", start: "12", duration: "4" },
  ];

  for (const sec of sections) {
    const idPattern = new RegExp(`id="${sec.id}"`);
    assert.match(html, idPattern, `section ${sec.id} must exist`);

    const sectionRegex = new RegExp(
      `<section[^>]*id="${sec.id}"[^>]*data-start="${sec.start}"[^>]*data-duration="${sec.duration}"`,
    );
    const altRegex = new RegExp(
      `<section[^>]*id="${sec.id}"[^>]*data-duration="${sec.duration}"[^>]*data-start="${sec.start}"`,
    );
    assert.ok(
      sectionRegex.test(html) || altRegex.test(html),
      `section ${sec.id} must have data-start="${sec.start}" and data-duration="${sec.duration}"`,
    );
  }
});

test("shot-recipes: recreated-ui has semantic article, header, button, cursor, typed text, and quoted highlight", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const sectionMatch = html.match(/<section[^>]*id="recreated-ui"[\s\S]*?<\/section>/);
  assert.ok(sectionMatch, "recreated-ui section must be present");
  const section = sectionMatch![0];

  assert.match(section, /<article[\s>]/, "must contain an <article> element");
  assert.match(section, /<header[\s>]/, "must contain a <header> element");
  assert.match(section, /<button[\s>]/, "must contain a <button> element");
  assert.match(section, /cursor/i, "must contain a cursor element or class");
  assert.match(section, /typed|typewriter|type-text/i, "must contain typed text mechanism");
  assert.match(section, /<blockquote[\s>]|quote-highlight|quoted/i, "must contain a quoted-element highlight");
});

test("shot-recipes: kinetic-quote has word-by-word reveal, source card, and GSAP keyframes", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const sectionMatch = html.match(/<section[^>]*id="kinetic-quote"[\s\S]*?<\/section>/);
  assert.ok(sectionMatch, "kinetic-quote section must be present");
  const section = sectionMatch![0];

  assert.match(section, /quote-word|word-reveal|kinetic|progressive/i, "must have progressive word reveal");
  assert.match(section, /source-card|publisher|attribution|source-info/i, "must have a source card with attribution");

  const script = getInlineScript(html);
  assert.ok(script.length > 0, "must have an inline script block");
  assert.match(script, /gsap\.(to|from|fromTo|timeline).*kinetic|kinetic.*gsap\.(to|from|fromTo|timeline)|#qw|#source-card/i, "must have GSAP animation for kinetic-quote");
});

test("shot-recipes: ken-burns uses project-owned SVG plate with scale/transform and vignette", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const sectionMatch = html.match(/<section[^>]*id="ken-burns"[\s\S]*?<\/section>/);
  assert.ok(sectionMatch, "ken-burns section must be present");
  const section = sectionMatch![0];

  assert.match(section, /archival-plate\.svg/, "must reference the project-owned SVG plate");
  assert.match(section, /scale|transform|ken-burns|pan|zoom/i, "must have Ken Burns scale/transform effect");
  assert.match(section, /vignette|highlight-mask|mask/i, "must have a vignette or highlight mask");

  const script = getInlineScript(html);
  assert.ok(script.length > 0, "must have an inline script block");
  assert.match(script, /gsap\.(to|from|fromTo).*ken|ken.*gsap\.(to|from|fromTo)|#plate-img|#highlight-mask|#plate-caption/i, "must have GSAP keyframes for ken-burns");
});

test("shot-recipes: news-lower-third has background, publisher, title, date, and GSAP keyframes", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const sectionMatch = html.match(/<section[^>]*id="news-lower-third"[\s\S]*?<\/section>/);
  assert.ok(sectionMatch, "news-lower-third section must be present");
  const section = sectionMatch![0];

  assert.match(section, /background|bg|gradient|solid/i, "must have a project-owned background");
  assert.match(section, /publisher|source-name|network/i, "must have publisher name field");
  assert.match(section, /clip-title|title-field|headline/i, "must have clip title field");
  assert.match(section, /date|year|timestamp/i, "must have date field");

  const script = getInlineScript(html);
  assert.ok(script.length > 0, "must have an inline script block");
  assert.match(script, /gsap\.(to|from|fromTo).*news|news.*gsap\.(to|from|fromTo)|lower.?third|#lower-third|#news-kicker|#news-headline/i, "must have GSAP keyframes for news-lower-third");
});

test("shot-recipes: every visible annotation is at least 28px font-size", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const fontSizeMatches = html.match(/font-size:\s*(\d+)px/g);
  assert.ok(fontSizeMatches, "must have font-size declarations");

  for (const decl of fontSizeMatches!) {
    const size = parseInt(decl.replace(/font-size:\s*/, "").replace("px", ""), 10);
    assert.ok(size >= 28, `font-size ${size}px is below the 28px minimum: ${decl}`);
  }
});

test("shot-recipes: no asset URL uses HTTP(S)", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const httpUrls = html.match(/https?:\/\/[^\s"'<>]+/g);
  assert.equal(httpUrls, null, `must not contain any HTTP(S) URLs, found: ${httpUrls?.join(", ")}`);
});

test("shot-recipes: GSAP keyframes use deterministic section-relative times (0, 4, 8, 12)", async () => {
  if (!html) html = await readFile(HTML_PATH, "utf-8");

  const script = getInlineScript(html);
  assert.ok(script.length > 0, "must have an inline script block");

  for (const sectionStart of [0, 4, 8, 12]) {
    const pattern = new RegExp(`\\b${sectionStart}(?:\\.0)?\\b`);
    assert.ok(pattern.test(script), `script must reference section start time ${sectionStart}`);
  }
});

test("shot-recipes: project.json exists and is valid", async () => {
  const projectPath = join(ROOT, "project.json");
  const content = await readFile(projectPath, "utf-8");
  const project = JSON.parse(content);
  assert.equal(project.id, "shot-recipes", "project id must be 'shot-recipes'");
  assert.ok(project.name, "project must have a name");
});

test("shot-recipes: assets directory contains gsap.min.js and archival-plate.svg", async () => {
  const gsapPath = join(ROOT, "assets", "gsap.min.js");
  const svgPath = join(ROOT, "assets", "archival-plate.svg");

  const gsapContent = await readFile(gsapPath, "utf-8");
  assert.ok(gsapContent.length > 0, "gsap.min.js must not be empty");

  const svgContent = await readFile(svgPath, "utf-8");
  assert.match(svgContent, /<svg/, "archival-plate.svg must be a valid SVG");
});

test("shot-recipes: qa directory exists with .gitkeep", async () => {
  const { stat } = await import("node:fs/promises");
  const qaPath = join(ROOT, "qa", ".gitkeep");
  const s = await stat(qaPath);
  assert.ok(s.isFile(), "qa/.gitkeep must exist");
});
