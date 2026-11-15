import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { safeFetch } from "../src/net-http.ts";
import { BoundedFetchError } from "../src/net.ts";

const publicDns = (host: string) => (host === "api.example.org" ? ["93.184.216.34"] : ["127.0.0.1"]);

test("only allowlisted hosts are fetched", async () => {
  await assert.rejects(
    () => safeFetch("https://other.example/data", { allowedHosts: ["api.example.org"] }, { resolver: publicDns, transport: async () => ({ status: 200, headers: {}, body: Buffer.from("{}") }) }),
    /host not allowed/
  );
});

test("redirects to an internal address are refused", async () => {
  const calls: string[] = [];
  const transport = async (target: { url: string }) => {
    calls.push(target.url);
    if (target.url.endsWith("/start")) return { status: 302, headers: { location: "http://169.254.169.254/meta" }, body: Buffer.alloc(0) };
    return { status: 200, headers: {}, body: Buffer.alloc(0) };
  };
  await assert.rejects(
    () => safeFetch("https://api.example.org/start", undefined, { resolver: publicDns, transport }),
    /blocked address/
  );
  assert.deepEqual(calls, ["https://api.example.org/start"]);
});

test("success returns the decoded body and its real digest", async () => {
  const payload = Buffer.from('{"ok":true}');
  const doc = await safeFetch(
    "https://api.example.org/data",
    { allowedHosts: ["api.example.org"], maxBytes: 1024 },
    { resolver: publicDns, transport: async () => ({ status: 200, headers: {}, body: payload }) }
  );
  assert.equal(doc.body, '{"ok":true}');
  assert.equal(doc.bytes, payload.byteLength);
  assert.equal(doc.sha256, createHash("sha256").update(payload).digest("hex"));
});

test("non-2xx and oversized bodies fail instead of returning partial data", async () => {
  await assert.rejects(
    () => safeFetch("https://api.example.org/x", { allowedHosts: ["api.example.org"] }, { resolver: publicDns, transport: async () => ({ status: 404, headers: {}, body: Buffer.alloc(0) }) }),
    BoundedFetchError
  );
  await assert.rejects(
    () => safeFetch("https://api.example.org/x", { allowedHosts: ["api.example.org"], maxBytes: 2048 }, { resolver: publicDns, transport: async () => ({ status: 200, headers: {}, body: Buffer.alloc(4096) }) }),
    /exceeds/
  );
});

test("redirect loops stop at the budget", async () => {
  const transport = async () => ({ status: 302, headers: { location: "https://api.example.org/loop" }, body: Buffer.alloc(0) });
  await assert.rejects(
    () => safeFetch("https://api.example.org/loop", { allowedHosts: ["api.example.org"], maxRedirects: 2 }, { resolver: publicDns, transport }),
    /too many redirects/
  );
});
