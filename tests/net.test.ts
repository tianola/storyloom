import assert from "node:assert/strict";
import { test } from "node:test";
import { assertSafeFetchTarget, BoundedFetchError, planFetch } from "../src/net.ts";

const publicDns = () => ["93.184.216.34"];

test("only http and https targets are allowed", () => {
  for (const url of ["file:///C:/secrets", "ftp://example.com/x", "http://example.com", "https://example.com"]) {
    const isHttp = url.startsWith("http");
    if (isHttp) assert.doesNotThrow(() => assertSafeFetchTarget(url, publicDns));
    else assert.throws(() => assertSafeFetchTarget(url, publicDns), /unsupported protocol/);
  }
});

test("credentials and query-less targets cannot smuggle a host change", () => {
  assert.throws(() => assertSafeFetchTarget("https://user:pass@example.com/", publicDns), /userinfo/);
  assert.throws(() => assertSafeFetchTarget("https://example.com:0/", publicDns), /port/);
  assert.throws(() => assertSafeFetchTarget("https://not a url", publicDns), /invalid url/);
});

test("loopback, private, link-local and reserved addresses are refused", () => {
  const hosts: [string, string[]][] = [
    ["http://127.0.0.1/admin", ["127.0.0.1"]],
    ["http://localhost/admin", ["127.0.0.1"]],
    ["http://169.254.169.254/latest/meta-data", ["169.254.169.254"]],
    ["http://10.1.2.3/", ["10.1.2.3"]],
    ["http://192.168.1.10/", ["192.168.1.10"]],
    ["http://172.16.5.5/", ["172.16.5.5"]],
    ["http://[::1]/", ["::1"]],
    ["http://[fd00::1234:abcd]/", ["fd00::1234:abcd"]],
    ["http://0.0.0.0/", ["0.0.0.0"]],
    ["http://100.64.0.1/", ["100.64.0.1"]],
    ["http://240.0.0.1/", ["240.0.0.1"]]
  ];
  for (const [url, addresses] of hosts) {
    assert.throws(() => assertSafeFetchTarget(url, () => addresses), /blocked address/, url);
  }
});

test("dns rebinding is caught because resolution happens before the request", () => {
  let call = 0;
  const rebinding = () => {
    call += 1;
    return call === 1 ? ["93.184.216.34"] : ["127.0.0.1"];
  };
  assert.throws(() => assertSafeFetchTarget("https://rebind.example/", rebinding), /blocked address/);
});

test("responses are bounded by size, timeout and redirect count", () => {
  const plan = planFetch("https://example.com/report", { maxBytes: 2_000_000, timeoutMs: 8000, maxRedirects: 3 });
  assert.deepEqual(plan, { url: "https://example.com/report", maxBytes: 2_000_000, timeoutMs: 8000, maxRedirects: 3, signal: plan.signal });
  assert.throws(() => planFetch("https://example.com", { maxBytes: 0, timeoutMs: 1000, maxRedirects: 2 }), BoundedFetchError);
  assert.throws(() => planFetch("https://example.com", { maxBytes: 1000, timeoutMs: 1000, maxRedirects: 21 }), BoundedFetchError);
});

test("redirect targets must pass the same checks as the first request", () => {
  const first = assertSafeFetchTarget("https://example.com/a", publicDns);
  assert.equal(first.hostname, "example.com");
  assert.throws(() => assertSafeFetchTarget("http://127.0.0.1/b", publicDns), /blocked address/);
  assert.throws(() => assertSafeFetchTarget("https://other.example/c", publicDns, { allowedHosts: ["example.com"] }), /host not allowed/);
});
