import { promises as dns } from "node:dns";
import type { LookupFunction } from "node:net";
import { request as httpsRequest } from "node:https";
import { request as httpRequest } from "node:http";
import { createHash } from "node:crypto";
import { assertSafeFetchTarget, BoundedFetchError, planFetch, type SafeTarget } from "./net.ts";

export type FetchedDocument = { url: string; status: number; body: string; bytes: number; sha256: string };

export type FetchOptions = {
  maxBytes: number;
  timeoutMs: number;
  maxRedirects: number;
  allowedHosts: string[];
};

export type Resolver = (host: string) => string[] | Promise<string[]>;
export type Transport = (target: SafeTarget, signal: AbortSignal) => Promise<{ status: number; headers: Record<string, string>; body: Uint8Array }>;

const LIMITS: FetchOptions = { maxBytes: 8 * 1024 * 1024, timeoutMs: 12_000, maxRedirects: 3, allowedHosts: [] };

const lookupAll: Resolver = async (host) => {
  const records = await dns.lookup(host, { all: true, verbatim: true });
  return records.map((record) => record.address);
};

type LookupCallback = (error: Error | null, address: string | Array<{ address: string; family: number }>, family?: number) => void;

function pinnedLookup(addresses: string[]): LookupFunction {
  const address = addresses[0]!;
  const family = address.includes(":") ? 6 : 4;
  return ((_hostname: string, options?: unknown, second?: unknown) => {
    const callback = (typeof options === "function" ? options : second) as LookupCallback;
    const wantsAll = typeof options === "object" && options !== null && "all" in options && (options as { all?: boolean }).all === true;
    if (wantsAll) callback(null, [{ address, family }]);
    else callback(null, address, family);
  }) as unknown as LookupFunction;
}

const nodeTransport: Transport = (target, signal) =>
  new Promise((resolve, reject) => {
    const client = target.protocol === "https:" ? httpsRequest : httpRequest;
    const req = client(target.url, { signal, servername: target.hostname, lookup: pinnedLookup(target.addresses) }, (res) => {
      const chunks: Buffer[] = [];
      let received = 0;
      res.on("data", (chunk: Buffer) => {
        received += chunk.length;
        if (received > LIMITS.maxBytes) {
          res.destroy(new BoundedFetchError("response exceeded the byte ceiling"));
          return;
        }
        chunks.push(chunk);
      });
      res.on("end", () =>
        resolve({
          status: res.statusCode ?? 0,
          headers: Object.fromEntries(Object.entries(res.headers).map(([key, value]) => [key, String(value)])),
          body: Buffer.concat(chunks)
        })
      );
    });
    req.on("error", reject);
    req.end();
  });

export async function safeFetch(rawUrl: string, overrides?: Partial<FetchOptions>, deps?: { transport?: Transport; resolver?: Resolver }): Promise<FetchedDocument> {
  const options: FetchOptions = { ...LIMITS, ...overrides };
  planFetch(rawUrl, { maxBytes: options.maxBytes, timeoutMs: options.timeoutMs, maxRedirects: options.maxRedirects });
  const run = deps?.transport ?? nodeTransport;
  const resolve = deps?.resolver ?? lookupAll;

  let current = rawUrl;
  for (let hop = 0; hop <= options.maxRedirects; hop += 1) {
    const preliminary = assertSafeFetchTarget(current, undefined, { allowedHosts: options.allowedHosts, skipAddressCheck: true });
    const addresses = await resolve(preliminary.hostname);
    if (addresses.length === 0) throw new BoundedFetchError(`no addresses resolved for ${preliminary.hostname}`);
    const target = assertSafeFetchTarget(preliminary.url, () => addresses, { allowedHosts: options.allowedHosts });
    const response = await run(target, AbortSignal.timeout(options.timeoutMs));

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.location;
      if (!location) throw new BoundedFetchError(`redirect without location from ${target.url}`);
      current = new URL(location, target.url).toString();
      continue;
    }
    if (response.status < 200 || response.status >= 300) throw new BoundedFetchError(`fetch failed with status ${response.status} for ${target.url}`);
    if (response.body.byteLength > options.maxBytes) throw new BoundedFetchError(`response body exceeds ${options.maxBytes} bytes`);
    return {
      url: target.url,
      status: response.status,
      body: new TextDecoder("utf-8").decode(response.body),
      bytes: response.body.byteLength,
      sha256: createHash("sha256").update(response.body).digest("hex")
    };
  }
  throw new BoundedFetchError(`too many redirects starting from ${rawUrl}`);
}
