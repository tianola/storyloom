import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { runProcess } from "../src/run.ts";

const GRANDCHILD = `
const { appendFileSync } = require("node:fs");
const child = require("node:child_process");
const marker = process.argv[1];
const grand = child.spawn(process.execPath, ["-e", "setInterval(() => { try { require('node:fs').appendFileSync(process.argv[1], 'x'); } catch {} }, 100)", marker], { stdio: "ignore", detached: false });
grand.on("exit", () => process.exit(0));
setTimeout(() => process.exit(0), 20_000);
`;

test("cancelling a run kills the whole process tree, not only the launcher", { skip: process.platform !== "win32" }, async () => {
  const dir = await mkdtemp(join(tmpdir(), "tree-kill-"));
  const marker = join(dir, "heartbeat");
  await writeFile(marker, "", "utf8");

  const controller = new AbortController();
  const running = runProcess([process.execPath, "-e", GRANDCHILD, marker], { signal: controller.signal });
  await new Promise((resolve) => setTimeout(resolve, 1_500));
  const before = (await readFile(marker, "utf8")).length;
  assert.ok(before >= 3, `the grandchild only wrote ${before} beats before the cancel`);

  controller.abort();
  await running;
  // a surviving grandchild beats every 100 ms, so three seconds of survival is ~30 beats
  await new Promise((resolve) => setTimeout(resolve, 3_000));
  const after = (await readFile(marker, "utf8")).length;
  assert.ok(after - before <= 3, `the grandchild survived the cancel and wrote ${after - before} more beats`);
});

test("a run that is not cancelled completes and reports its exit code", async () => {
  const result = await runProcess([process.execPath, "-e", "console.log('hi'); process.exit(3)"]);
  assert.equal(result.code, 3);
  assert.equal(result.stdout.trim(), "hi");
});
