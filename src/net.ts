import { isIP } from "node:net";

export class BoundedFetchError extends Error {}

export type FetchPlan = { url: string; maxBytes: number; timeoutMs: number; maxRedirects: number; signal: AbortSignal };
export type SafeTarget = { url: string; hostname: string; protocol: "http:" | "https:"; addresses: string[] };
type Resolver = (host: string) => string[];

const MAX_BYTES_LIMIT = 50 * 1024 * 1024;

function blockedIpv4(address: string): boolean {
  const parts = address.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return true;
  const [a = 0, b = 0] = parts;
  if (a === 0) return true;
  if (a === 10) return true;
  if (a === 127) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 100 && b >= 64 && b <= 127) return true;
  if (a === 192 && b === 0 && (parts[2] === 2 || parts[2] === 3)) return true;
  if (a === 198 && (b === 18 || b === 19)) return true;
  if (a === 198 && b === 51 && parts[2] === 100) return true;
  if (a === 203 && b === 0 && parts[2] === 113) return true;
  if (a >= 224) return true;
  return false;
}

function blockedIpv6(address: string): boolean {
  const value = address.toLowerCase();
  if (value === "::" || value === "::1") return true;
  const mapped = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/.exec(value);
  if (mapped?.[1]) return blockedIpv4(mapped[1]);
  const head = value.split(":")[0] ?? "";
  if (/^f[cd][0-9a-f]{2}:/.test(value) || /^f[cd]/.test(head) && head.length === 4) return true;
  if (value.startsWith("fe8") || value.startsWith("fe9") || value.startsWith("fea") || value.startsWith("feb")) return true;
  if (value.startsWith("ff")) return true;
  if (value.startsWith("2001:db8:")) return true;
  return false;
}

export function isBlockedAddress(address: string): boolean {
  const version = isIP(address);
  if (version === 0) return true;
  return version === 4 ? blockedIpv4(address) : blockedIpv6(address);
}

export function assertSafeFetchTarget(
  rawUrl: string,
  resolver?: Resolver,
  options?: { allowedHosts?: string[]; skipAddressCheck?: boolean }
): SafeTarget {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new BoundedFetchError(`invalid url: ${rawUrl}`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new BoundedFetchError(`unsupported protocol: ${url.protocol}`);
  if (url.username !== "" || url.password !== "") throw new BoundedFetchError("userinfo is not allowed");
  if (url.port !== "" && url.port !== "80" && url.port !== "443") throw new BoundedFetchError(`port not allowed: ${url.port}`);

  const hostname = url.hostname.replace(/^\[|\]$/g, "");
  if (hostname === "") throw new BoundedFetchError(`invalid url: ${rawUrl}`);
  if (options?.allowedHosts?.length && !options.allowedHosts.includes(hostname)) throw new BoundedFetchError(`host not allowed: ${hostname}`);
  if (options?.skipAddressCheck) return { url: url.toString(), hostname, protocol: url.protocol, addresses: [] };
  if (!resolver) throw new BoundedFetchError(`a resolver is required to validate ${hostname}`);

  const first = isIP(hostname) ? [hostname] : resolver(hostname);
  const second = isIP(hostname) ? first : resolver(hostname);
  if (first.length === 0 || second.length === 0) throw new BoundedFetchError(`no addresses resolved for ${hostname}`);
  const stable = first.slice().sort().join(",") === second.slice().sort().join(",");
  const addresses = [...new Set([...first, ...second])];
  for (const address of addresses) {
    if (isBlockedAddress(address)) throw new BoundedFetchError(`blocked address: ${address}`);
  }
  if (!stable) throw new BoundedFetchError(`blocked address: resolution changed between checks`);
  return { url: url.toString(), hostname, protocol: url.protocol, addresses };
}

export function planFetch(
  rawUrl: string,
  limits: { maxBytes: number; timeoutMs: number; maxRedirects: number }
): FetchPlan {
  const { maxBytes, timeoutMs, maxRedirects } = limits;
  if (!Number.isInteger(maxBytes) || maxBytes < 1024 || maxBytes > MAX_BYTES_LIMIT) throw new BoundedFetchError(`maxBytes must be between 1024 and ${MAX_BYTES_LIMIT}`);
  if (!Number.isInteger(timeoutMs) || timeoutMs < 250 || timeoutMs > 60_000) throw new BoundedFetchError("timeoutMs must be between 250 and 60000");
  if (!Number.isInteger(maxRedirects) || maxRedirects < 0 || maxRedirects > 5) throw new BoundedFetchError("maxRedirects must be between 0 and 5");
  return { url: rawUrl, maxBytes, timeoutMs, maxRedirects, signal: AbortSignal.timeout(timeoutMs) };
}
