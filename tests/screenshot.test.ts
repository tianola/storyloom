import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { test } from "node:test";

const helper = fileURLToPath(new URL("../tools/sourcing/screenshot.mjs", import.meta.url));
const repository = fileURLToPath(new URL("..", import.meta.url));

test("screenshot helper captures a full-page local HTML fixture as PNG", (t) => {
  const temporary = mkdtempSync(join(tmpdir(), "sourcing-screenshot-"));
  t.after(() => rmSync(temporary, { recursive: true, force: true }));
  const fixture = join(temporary, "fixture.html");
  const output = join(temporary, "capture.png");
  writeFileSync(fixture, `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Screenshot fixture</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Arial, sans-serif; color: #f4f1e8; background: #101d2c; }
  main { min-height: 1500px; padding: 64px; background: linear-gradient(135deg, #101d2c, #274c5e 55%, #a15c36); }
  h1 { font-size: 72px; max-width: 1100px; }
  p { font-size: 30px; line-height: 1.5; max-width: 1050px; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 56px; }
  .card { min-height: 240px; padding: 30px; border: 3px solid #d8bd74; border-radius: 18px; background: #ffffff18; font-size: 24px; }
</style></head><body><main>
<h1>The Carrington Event: an accessible local screenshot fixture</h1>
<p>This deterministic page exercises full-page browser capture without a remote request, authentication, or paid provider.</p>
<div class="grid">
  <section class="card">1859<br>Solar observations and telegraph disruption.</section>
  <section class="card">Mechanism<br>Solar eruption, magnetic field, induced current.</section>
  <section class="card">Rights<br>Source, licence review, and attribution metadata.</section>
  <section class="card">Archive<br>Historical documents with item-level provenance.</section>
  <section class="card">Diagram<br>Original graphics built from verified facts.</section>
  <section class="card">Purchase gate<br>Preview media must be replaced before upload.</section>
</div>
<p>Additional page height makes the full-page capture meaningfully larger than a minimal blank image.</p>
</main></body></html>`, "utf8");

  const result = spawnSync(process.execPath, [helper, "--url", pathToFileURL(fixture).href, "--out", output], {
    cwd: repository,
    encoding: "utf8",
    timeout: 60_000,
  });
  assert.equal(result.status, 0, `screenshot helper failed: ${result.stderr || result.stdout}`);
  const png = readFileSync(output);
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.ok(statSync(output).size > 1_000, `PNG was only ${statSync(output).size} bytes`);
});
